import SwiftUI

// MARK: - Rezepte

struct RecipesView: View {
    @EnvironmentObject var store: DataStore
    @State private var showAdd   = false
    @State private var editItem: Recipe? = nil
    @State private var search    = ""

    private var filtered: [Recipe] {
        search.isEmpty ? store.recipes : store.recipes.filter {
            $0.name.localizedCaseInsensitiveContains(search)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if store.recipes.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "book.closed").font(.system(size: 64)).foregroundStyle(.secondary)
                        Text("Noch keine Rezepte").font(.title3).foregroundStyle(.secondary)
                        Button("Erstes Rezept erstellen") { showAdd = true }
                            .buttonStyle(.borderedProminent).tint(.purple)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(filtered) { recipe in
                            RecipeRow(recipe: recipe)
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) { store.deleteRecipe(recipe) } label: {
                                        Label("Löschen", systemImage: "trash")
                                    }
                                    Button { editItem = recipe } label: {
                                        Label("Bearbeiten", systemImage: "pencil")
                                    }
                                    .tint(.orange)
                                }
                        }
                    }
                    .searchable(text: $search, prompt: "Rezept suchen")
                }
            }
            .navigationTitle("Rezepte")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { showAdd = true } label: { Image(systemName: "plus") }
                }
            }
            .sheet(isPresented: $showAdd) { AddEditRecipeView() }
            .sheet(item: $editItem) { recipe in AddEditRecipeView(existing: recipe) }
        }
    }
}

// MARK: - Rezept-Zeile

private struct RecipeRow: View {
    let recipe: Recipe

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(recipe.name).font(.headline)
                Spacer()
                Text(String(format: "%.1f Pkt./Portion", recipe.pointsPerServing))
                    .font(.subheadline)
                    .foregroundStyle(.purple)
            }
            HStack(spacing: 12) {
                Label("\(recipe.servings) Portionen", systemImage: "person.2")
                Label("\(recipe.ingredients.count) Zutaten", systemImage: "list.bullet")
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Rezept erstellen / bearbeiten

struct AddEditRecipeView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss

    let existing: Recipe?

    init(existing: Recipe? = nil) {
        self.existing = existing
        if let e = existing {
            _name         = State(initialValue: e.name)
            _category     = State(initialValue: e.category)
            _servings     = State(initialValue: e.servings)
            _instructions = State(initialValue: e.instructions)
            _ingredients  = State(initialValue: e.ingredients)
        }
    }

    @State private var name         = ""
    @State private var category     = FoodCategory.other
    @State private var servings     = 2
    @State private var instructions = ""
    @State private var ingredients: [RecipeIngredient] = []
    @State private var showFoodPicker = false

    private var totalPoints: Double { ingredients.reduce(0) { $0 + $1.points } }
    private var ptsPerServing: Double { servings > 0 ? totalPoints / Double(servings) : totalPoints }

    var body: some View {
        NavigationStack {
            Form {
                Section("Rezept-Info") {
                    TextField("Name", text: $name)
                    Picker("Kategorie", selection: $category) {
                        ForEach(FoodCategory.allCases) { cat in
                            Text(cat.emoji + " " + cat.rawValue).tag(cat)
                        }
                    }
                    Stepper("Portionen: \(servings)", value: $servings, in: 1...20)
                }

                Section {
                    ForEach(ingredients) { ing in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(ing.foodItemName)
                                Text("\(Int(ing.amount)) g")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(String(format: "%.1f Pkt.", ing.points))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .onDelete { idx in ingredients.remove(atOffsets: idx) }

                    Button { showFoodPicker = true } label: {
                        Label("Zutat hinzufügen", systemImage: "plus.circle")
                    }
                } header: {
                    HStack {
                        Text("Zutaten")
                        Spacer()
                        Text(String(format: "Gesamt: %.1f Pkt. | %.1f/Portion", totalPoints, ptsPerServing))
                            .font(.caption).foregroundStyle(.purple)
                    }
                }

                Section("Zubereitung") {
                    TextEditor(text: $instructions)
                        .frame(minHeight: 100)
                }
            }
            .navigationTitle(existing == nil ? "Neues Rezept" : "Rezept bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { save() }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .sheet(isPresented: $showFoodPicker) {
                IngredientPickerView { ingredient in
                    ingredients.append(ingredient)
                }
            }
        }
    }

    private func save() {
        var recipe = Recipe(
            id: existing?.id ?? UUID(),
            name: name, category: category, servings: servings,
            ingredients: ingredients, instructions: instructions)
        recipe.totalKcal = ingredients.reduce(0) { sum, ing in
            let factor = ing.amount / max(1, store.food(by: ing.foodItemId)?.portionSize ?? 100)
            return sum + (store.food(by: ing.foodItemId)?.kcal ?? 0) * factor
        }
        if existing != nil { store.updateRecipe(recipe) }
        else { store.addRecipe(recipe) }
        dismiss()
    }
}

// MARK: - Zutat auswählen

private struct IngredientPickerView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss
    let onSelect: (RecipeIngredient) -> Void

    @State private var search  = ""
    @State private var amount  = 100.0
    @State private var selected: FoodItem? = nil

    private var plan: UserProfile.PunktePlan { store.userProfile?.plan ?? .balanced }

    private var filtered: [FoodItem] {
        search.isEmpty ? store.foodItems :
            store.foodItems.filter { $0.name.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        NavigationStack {
            List {
                if let item = selected {
                    Section("Menge für '\(item.name)'") {
                        HStack {
                            TextField("g", value: $amount, format: .number)
                                .keyboardType(.decimalPad)
                            Text("g").foregroundStyle(.secondary)
                        }
                        let factor = amount / max(1, item.portionSize)
                        let pts = item.points(for: plan) * factor
                        Text(String(format: "%.1f Punkte", pts)).foregroundStyle(.purple)
                    }
                }
                ForEach(filtered) { item in
                    FoodRowView(item: item, plan: plan)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            selected = item
                            amount = item.portionSize
                        }
                        .background(selected?.id == item.id ? Color.purple.opacity(0.1) : .clear)
                }
            }
            .searchable(text: $search)
            .navigationTitle("Zutat wählen")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Hinzufügen") { addIngredient() }
                        .disabled(selected == nil)
                }
            }
        }
    }

    private func addIngredient() {
        guard let item = selected else { return }
        let factor = amount / max(1, item.portionSize)
        let pts = item.points(for: plan) * factor
        let ing = RecipeIngredient(foodItemId: item.id, foodItemName: item.name,
                                   amount: amount, points: pts)
        onSelect(ing)
        dismiss()
    }
}

import SwiftUI

// MARK: - Lebensmittel-Datenbank

struct FoodDatabaseView: View {
    @EnvironmentObject var store: DataStore
    @State private var search        = ""
    @State private var selectedCat: FoodCategory? = nil
    @State private var showAddFood   = false
    @State private var editItem: FoodItem? = nil

    private var plan: UserProfile.PunktePlan { store.userProfile?.plan ?? .balanced }

    private var filtered: [FoodItem] {
        var items = store.foodItems
        if let cat = selectedCat { items = items.filter { $0.category == cat } }
        if !search.isEmpty { items = items.filter { $0.name.localizedCaseInsensitiveContains(search) } }
        return items.sorted { $0.name < $1.name }
    }

    private var grouped: [(FoodCategory, [FoodItem])] {
        let cats = selectedCat != nil ? [selectedCat!] : FoodCategory.allCases
        return cats.compactMap { cat in
            let items = filtered.filter { $0.category == cat }
            return items.isEmpty ? nil : (cat, items)
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Kategorie-Scrollleiste
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        CategoryChip(label: "Alle", isSelected: selectedCat == nil) {
                            selectedCat = nil
                        }
                        ForEach(FoodCategory.allCases) { cat in
                            CategoryChip(label: cat.emoji + " " + cat.rawValue,
                                         isSelected: selectedCat == cat) {
                                selectedCat = selectedCat == cat ? nil : cat
                            }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                }

                List {
                    ForEach(grouped, id: \.0) { cat, items in
                        Section(cat.emoji + " " + cat.rawValue) {
                            ForEach(items) { item in
                                FoodRowView(item: item, plan: plan)
                                    .swipeActions(edge: .trailing) {
                                        if item.isCustom {
                                            Button(role: .destructive) {
                                                store.deleteFood(item)
                                            } label: {
                                                Label("Löschen", systemImage: "trash")
                                            }
                                            Button { editItem = item } label: {
                                                Label("Bearbeiten", systemImage: "pencil")
                                            }
                                            .tint(.orange)
                                        }
                                    }
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
            .searchable(text: $search, prompt: "Lebensmittel suchen")
            .navigationTitle("Lebensmittel")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { showAddFood = true } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showAddFood) {
                AddEditFoodView()
            }
            .sheet(item: $editItem) { item in
                AddEditFoodView(existing: item)
            }
        }
    }
}

// MARK: - Kategorie-Chip

struct CategoryChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? Color.purple : Color(.secondarySystemBackground))
                .foregroundStyle(isSelected ? .white : .primary)
                .clipShape(Capsule())
        }
    }
}

// MARK: - Lebensmittel-Zeile (wiederverwendbar)

struct FoodRowView: View {
    let item: FoodItem
    let plan: UserProfile.PunktePlan

    private var pts: Double { item.points(for: plan) }
    private var isZero: Bool { item.isZeroPoint(for: plan) }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.name)
                    .font(.subheadline)
                Text(item.portionDescription)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                if isZero {
                    Text("0-Punkte ✅")
                        .font(.caption.bold())
                        .foregroundStyle(.green)
                } else {
                    Text(pts == pts.rounded() ? "\(Int(pts))" : String(format: "%.1f", pts))
                        .font(.subheadline.bold())
                    Text("Punkte")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

// MARK: - Lebensmittel hinzufügen/bearbeiten

struct AddEditFoodView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss

    let existing: FoodItem?

    init(existing: FoodItem? = nil) {
        self.existing = existing
        if let e = existing {
            _name        = State(initialValue: e.name)
            _category    = State(initialValue: e.category)
            _portionSize = State(initialValue: e.portionSize)
            _portionDesc = State(initialValue: e.portionDescription)
            _kcal        = State(initialValue: e.kcal)
            _fat         = State(initialValue: e.fat)
            _satFat      = State(initialValue: e.saturatedFat)
            _carbs       = State(initialValue: e.carbs)
            _sugar       = State(initialValue: e.sugar)
            _protein     = State(initialValue: e.protein)
            _fiber       = State(initialValue: e.fiber)
            _useFormula  = State(initialValue: false)
        }
    }

    @State private var name        = ""
    @State private var category    = FoodCategory.other
    @State private var portionSize = 100.0
    @State private var portionDesc = "100 g"
    @State private var kcal        = 0.0
    @State private var fat         = 0.0
    @State private var satFat      = 0.0
    @State private var carbs       = 0.0
    @State private var sugar       = 0.0
    @State private var protein     = 0.0
    @State private var fiber       = 0.0
    @State private var useFormula  = true

    private var calculatedPoints: Double {
        PointsCalculator.calculatePoints(kcal: kcal, fat: fat, saturatedFat: satFat,
                                         sugar: sugar, protein: protein)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Grunddaten") {
                    TextField("Name", text: $name)
                    Picker("Kategorie", selection: $category) {
                        ForEach(FoodCategory.allCases) { cat in
                            Text(cat.emoji + " " + cat.rawValue).tag(cat)
                        }
                    }
                }

                Section("Portion") {
                    HStack {
                        Text("Portionsgröße")
                        Spacer()
                        TextField("g", value: $portionSize, format: .number)
                            .keyboardType(.decimalPad).frame(width: 70).multilineTextAlignment(.trailing)
                        Text("g").foregroundStyle(.secondary)
                    }
                    TextField("Beschreibung (z. B. 1 Scheibe)", text: $portionDesc)
                }

                Section("Nährwerte (pro Portion)") {
                    NutriField(label: "Kalorien (kcal)", value: $kcal, unit: "kcal")
                    NutriField(label: "Fett", value: $fat, unit: "g")
                    NutriField(label: "davon gesättigt", value: $satFat, unit: "g")
                    NutriField(label: "Kohlenhydrate", value: $carbs, unit: "g")
                    NutriField(label: "davon Zucker", value: $sugar, unit: "g")
                    NutriField(label: "Eiweiß", value: $protein, unit: "g")
                    NutriField(label: "Ballaststoffe", value: $fiber, unit: "g")
                }

                Section("Punkte") {
                    Toggle("Formel verwenden", isOn: $useFormula)
                    if useFormula {
                        HStack {
                            Text("Berechnete Punkte")
                            Spacer()
                            Text(String(format: "%.1f", calculatedPoints))
                                .foregroundStyle(.purple)
                                .bold()
                        }
                    }
                }
            }
            .navigationTitle(existing == nil ? "Lebensmittel hinzufügen" : "Bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { save() }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    private func save() {
        let pts = useFormula ? calculatedPoints : (existing?.punkteValue ?? 0)
        let item = FoodItem(
            id: existing?.id ?? UUID(),
            name: name,
            category: category,
            portionSize: portionSize,
            portionDescription: portionDesc,
            kcal: kcal, fat: fat, saturatedFat: satFat,
            carbs: carbs, sugar: sugar, protein: protein, fiber: fiber,
            punkteValue: pts, isCustom: true)

        if existing != nil { store.updateFood(item) }
        else { store.addFood(item) }
        dismiss()
    }
}

// MARK: - Nährwert-Eingabezeile

private struct NutriField: View {
    let label: String
    @Binding var value: Double
    let unit: String

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            TextField("0", value: $value, format: .number)
                .keyboardType(.decimalPad)
                .frame(width: 70)
                .multilineTextAlignment(.trailing)
            Text(unit).foregroundStyle(.secondary).frame(width: 30)
        }
    }
}

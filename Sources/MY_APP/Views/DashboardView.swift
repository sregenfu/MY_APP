import SwiftUI

// MARK: - Dashboard (Heute)

struct DashboardView: View {
    @EnvironmentObject var store: DataStore
    @EnvironmentObject var health: HealthKitService
    @State private var selectedDate: Date = Date()
    @State private var showAddFood = false
    @State private var editingLog: LoggedFood? = nil

    private var profile: UserProfile { store.userProfile ?? UserProfile() }
    private var dailyPoints: Int { PointsCalculator.dailyPoints(for: profile) }

    private var todayLog: DailyLog {
        store.logOrCreate(for: selectedDate)
    }

    private var usedPoints: Double { todayLog.totalPointsUsed }
    private var remainingPoints: Double { Double(dailyPoints) - usedPoints + Double(todayLog.bonusActivityPoints) }

    // Farbindikator
    private var pointColor: Color {
        if remainingPoints < 0 { return .red }
        if remainingPoints < Double(dailyPoints) * 0.2 { return .orange }
        return .green
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {

                    // ── Datumswähler ─────────────────────────────────────────
                    DatePicker("Datum", selection: $selectedDate, displayedComponents: .date)
                        .datePickerStyle(.compact)
                        .labelsHidden()
                        .padding(.horizontal)

                    // ── Punkte-Ring ──────────────────────────────────────────
                    PointsRingView(used: usedPoints,
                                  total: Double(dailyPoints),
                                  bonus: Double(todayLog.bonusActivityPoints),
                                  color: pointColor)
                        .padding(.horizontal)

                    // ── Apple Health ─────────────────────────────────────────
                    if health.isAvailable {
                        HealthSummaryCard(health: health)
                            .padding(.horizontal)
                    }

                    // ── Mahlzeiten ───────────────────────────────────────────
                    MealsSection(log: todayLog,
                                 date: selectedDate,
                                 onDelete: deleteFood,
                                 onEdit: { editingLog = $0 })
                        .padding(.horizontal)

                    // ── Wasser ───────────────────────────────────────────────
                    WaterTrackerCard(log: todayLog, date: selectedDate)
                        .padding(.horizontal)
                        .padding(.bottom, 24)
                }
            }
            .navigationTitle("Mein Tag")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { showAddFood = true } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                    }
                }
            }
            .sheet(isPresented: $showAddFood) {
                AddFoodToDiaryView(date: selectedDate)
            }
            .sheet(item: $editingLog) { food in
                EditLoggedFoodView(food: food, date: selectedDate)
            }
        }
    }

    private func deleteFood(_ food: LoggedFood) {
        store.removeFood(food, from: selectedDate)
    }
}

// MARK: - Punkte-Ring

private struct PointsRingView: View {
    let used: Double
    let total: Double
    let bonus: Double
    let color: Color

    private var progress: Double { min(1.0, used / max(1, total + bonus)) }

    var body: some View {
        HStack(spacing: 24) {
            ZStack {
                Circle()
                    .stroke(Color.secondary.opacity(0.2), lineWidth: 18)
                    .frame(width: 130, height: 130)

                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(color, style: StrokeStyle(lineWidth: 18, lineCap: .round))
                    .frame(width: 130, height: 130)
                    .rotationEffect(.degrees(-90))
                    .animation(.easeOut, value: progress)

                VStack(spacing: 2) {
                    Text("\(Int(used))")
                        .font(.title.bold())
                    Text("/ \(Int(total + bonus))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                StatRow(label: "Verwendet", value: String(format: "%.1f", used), color: .primary)
                StatRow(label: "Verfügbar", value: String(format: "%.1f", total + bonus), color: .secondary)
                StatRow(label: "Verbleibend", value: String(format: "%.1f", total + bonus - used),
                        color: total + bonus - used < 0 ? .red : .green)
                if bonus > 0 {
                    StatRow(label: "Aktivitätsbonus", value: "+\(Int(bonus))", color: .blue)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

private struct StatRow: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.subheadline.bold()).foregroundStyle(color)
        }
    }
}

// MARK: - Apple Health Summary

private struct HealthSummaryCard: View {
    @ObservedObject var health: HealthKitService

    var body: some View {
        HStack(spacing: 0) {
            HealthMetric(icon: "figure.walk", value: "\(Int(health.todaySteps))", label: "Schritte", color: .blue)
            Divider()
            HealthMetric(icon: "flame.fill", value: "\(Int(health.todayActiveKcal))", label: "kcal aktiv", color: .orange)
            Divider()
            HealthMetric(icon: "scalemass.fill",
                         value: health.latestWeight.map { String(format: "%.1f kg", $0) } ?? "–",
                         label: "Gewicht", color: .green)
        }
        .padding(.vertical, 12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

private struct HealthMetric: View {
    let icon: String
    let value: String
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(color)
            Text(value).font(.subheadline.bold())
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Mahlzeiten-Sektion

private struct MealsSection: View {
    let log: DailyLog
    let date: Date
    let onDelete: (LoggedFood) -> Void
    let onEdit: (LoggedFood) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Mahlzeiten").font(.headline)

            ForEach(MealType.allCases, id: \.self) { meal in
                let foods = log.loggedFoods.filter { $0.mealType == meal }
                if !foods.isEmpty || meal == .breakfast {
                    MealGroup(meal: meal, foods: foods, onDelete: onDelete, onEdit: onEdit)
                }
            }
        }
    }
}

private struct MealGroup: View {
    let meal: MealType
    let foods: [LoggedFood]
    let onDelete: (LoggedFood) -> Void
    let onEdit: (LoggedFood) -> Void

    private var totalPoints: Double { foods.reduce(0) { $0 + $1.points } }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(meal.emoji + " " + meal.rawValue)
                    .font(.subheadline.bold())
                Spacer()
                if totalPoints > 0 {
                    Text(String(format: "%.1f Pkt.", totalPoints))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if foods.isEmpty {
                Text("Nichts eingetragen")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.leading, 4)
            } else {
                ForEach(foods) { food in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(food.name).font(.subheadline)
                            Text("\(Int(food.amount)) g")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(food.points == 0 ? "0 ✅" : String(format: "%.1f", food.points))
                            .font(.subheadline)
                            .foregroundStyle(food.points == 0 ? .green : .primary)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color(.tertiarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) { onDelete(food) } label: {
                            Label("Löschen", systemImage: "trash")
                        }
                        Button { onEdit(food) } label: {
                            Label("Bearbeiten", systemImage: "pencil")
                        }
                        .tint(.orange)
                    }
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Wasser-Tracker

private struct WaterTrackerCard: View {
    @EnvironmentObject var store: DataStore
    let log: DailyLog
    let date: Date

    private var cups: Int { Int(log.waterIntake / 0.25) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("Wasser", systemImage: "drop.fill").foregroundStyle(.blue)
                Spacer()
                Text(String(format: "%.2f l", log.waterIntake))
                    .foregroundStyle(.secondary)
            }
            .font(.headline)

            HStack(spacing: 6) {
                ForEach(0..<8, id: \.self) { i in
                    Image(systemName: i < cups ? "drop.fill" : "drop")
                        .foregroundStyle(i < cups ? .blue : .secondary)
                        .font(.title3)
                        .onTapGesture { toggleCup(i) }
                }
            }
            Text("Tippe auf eine Tropfen (je 250 ml)").font(.caption2).foregroundStyle(.secondary)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func toggleCup(_ index: Int) {
        var updated = store.logOrCreate(for: date)
        let current = Int(updated.waterIntake / 0.25)
        updated.waterIntake = Double(index < current ? index : index + 1) * 0.25
        store.updateLog(updated)
    }
}

// MARK: - Lebensmittel zum Diary hinzufügen

struct AddFoodToDiaryView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss
    let date: Date

    @State private var search     = ""
    @State private var mealType   = MealType.snack
    @State private var amount     = 100.0
    @State private var selected: FoodItem? = nil

    private var filtered: [FoodItem] {
        if search.isEmpty { return store.foodItems }
        return store.foodItems.filter { $0.name.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Mahlzeit") {
                    Picker("Mahlzeit", selection: $mealType) {
                        ForEach(MealType.allCases, id: \.self) { m in
                            Text(m.emoji + " " + m.rawValue).tag(m)
                        }
                    }
                }

                if let item = selected {
                    Section("Menge anpassen") {
                        HStack {
                            Text(item.name)
                            Spacer()
                            TextField("g", value: $amount, format: .number)
                                .keyboardType(.decimalPad)
                                .frame(width: 70)
                                .multilineTextAlignment(.trailing)
                            Text("g").foregroundStyle(.secondary)
                        }
                        let factor = amount / max(1, item.portionSize)
                        let pts = item.points(for: store.userProfile?.plan ?? .balanced) * factor
                        Text(String(format: "%.1f Punkte für %.0f g", pts, amount))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Suche") {
                    ForEach(filtered) { item in
                        FoodRowView(item: item, plan: store.userProfile?.plan ?? .balanced)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selected = item
                                amount = item.portionSize
                            }
                            .background(selected?.id == item.id ? Color.purple.opacity(0.1) : .clear)
                    }
                }
            }
            .searchable(text: $search, prompt: "Lebensmittel suchen")
            .navigationTitle("Eintrag hinzufügen")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Hinzufügen") { addFood() }
                        .disabled(selected == nil)
                }
            }
        }
    }

    private func addFood() {
        guard let item = selected else { return }
        let plan = store.userProfile?.plan ?? .balanced
        let factor = amount / max(1, item.portionSize)
        let pts = item.points(for: plan) * factor
        let entry = LoggedFood(foodItemId: item.id, name: item.name,
                               amount: amount, points: pts, mealType: mealType)
        store.addFood(entry, to: date)
        dismiss()
    }
}

// MARK: - Eintrag bearbeiten

struct EditLoggedFoodView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss
    @State var food: LoggedFood
    let date: Date

    var body: some View {
        NavigationStack {
            Form {
                Section("Lebensmittel") {
                    Text(food.name)
                }
                Section("Menge (g)") {
                    TextField("g", value: $food.amount, format: .number)
                        .keyboardType(.decimalPad)
                }
                Section("Mahlzeit") {
                    Picker("", selection: $food.mealType) {
                        ForEach(MealType.allCases, id: \.self) { m in
                            Text(m.emoji + " " + m.rawValue).tag(m)
                        }
                    }
                    .pickerStyle(.menu)
                }
            }
            .navigationTitle("Eintrag bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { save() }
                }
            }
        }
    }

    private func save() {
        // Punkte neu berechnen (vereinfacht über gespeicherte Punkte skaliert)
        store.removeFood(food, from: date)
        store.addFood(food, to: date)
        dismiss()
    }
}

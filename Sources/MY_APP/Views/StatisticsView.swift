import SwiftUI

// MARK: - Statistik & Ziele

struct StatisticsView: View {
    @EnvironmentObject var store: DataStore
    @EnvironmentObject var health: HealthKitService
    @State private var showAddWeight = false
    @State private var editEntry: WeightEntry? = nil

    private var profile: UserProfile { store.userProfile ?? UserProfile() }

    private var sortedWeights: [WeightEntry] {
        store.weightEntries.sorted { $0.date > $1.date }
    }

    private var stars: Int {
        PointsCalculator.starsEarned(startWeight: profile.startWeight,
                                     currentWeight: profile.currentWeight)
    }

    private var percent: Double {
        PointsCalculator.percentToGoal(startWeight: profile.startWeight,
                                       currentWeight: profile.currentWeight,
                                       goalWeight: profile.goalWeight)
    }

    private var remaining: Double {
        PointsCalculator.remainingToGoal(currentWeight: profile.currentWeight,
                                         goalWeight: profile.goalWeight)
    }

    private var lostTotal: Double {
        max(0, profile.startWeight - profile.currentWeight)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {

                    // ── Sterne-Banner ────────────────────────────────────────
                    StarsBannerView(stars: stars, lost: lostTotal)
                        .padding(.horizontal)

                    // ── Fortschrittsbalken ───────────────────────────────────
                    GoalProgressCard(percent: percent, remaining: remaining,
                                     start: profile.startWeight,
                                     current: profile.currentWeight,
                                     goal: profile.goalWeight)
                        .padding(.horizontal)

                    // ── Apple Health Verlauf ─────────────────────────────────
                    if health.isAuthorized && !health.weightHistory.isEmpty {
                        WeightChartCard(history: health.weightHistory)
                            .padding(.horizontal)
                    }

                    // ── Wochen-Stats ─────────────────────────────────────────
                    WeeklyStatsCard()
                        .padding(.horizontal)

                    // ── Gewichtsprotokoll ────────────────────────────────────
                    WeightLogSection(entries: sortedWeights,
                                     onDelete: store.deleteWeight,
                                     onEdit: { editEntry = $0 })
                        .padding(.horizontal)
                        .padding(.bottom, 24)
                }
            }
            .navigationTitle("Statistik & Ziele")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { showAddWeight = true } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showAddWeight) { AddWeightView() }
            .sheet(item: $editEntry) { entry in EditWeightView(entry: entry) }
        }
    }
}

// MARK: - Sterne-Banner

private struct StarsBannerView: View {
    let stars: Int
    let lost: Double

    var body: some View {
        VStack(spacing: 12) {
            Text("Meine Erfolge")
                .font(.headline)

            HStack(spacing: 6) {
                ForEach(0..<max(1, stars + 2), id: \.self) { i in
                    Image(systemName: i < stars ? "star.fill" : "star")
                        .foregroundStyle(i < stars ? .yellow : .secondary)
                        .font(.title2)
                }
            }

            if stars > 0 {
                Text("🏆 \(stars) × 5 kg abgenommen!")
                    .font(.subheadline.bold())
                    .foregroundStyle(.orange)
            }

            Text(String(format: "Insgesamt abgenommen: %.1f kg", lost))
                .font(.caption)
                .foregroundStyle(.secondary)

            // Meilensteine
            let nextKg = PointsCalculator.kgToNextMilestone(
                startWeight: lost + (UserDefaults.standard.double(forKey: "startWeight")),
                currentWeight: lost + (UserDefaults.standard.double(forKey: "startWeight"))
            )
            if lost > 0 {
                Text(String(format: "Noch %.1f kg bis zum nächsten Stern ⭐", 5 - lost.truncatingRemainder(dividingBy: 5)))
                    .font(.caption)
                    .foregroundStyle(.purple)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(colors: [.purple.opacity(0.15), .orange.opacity(0.1)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Ziel-Fortschritt

private struct GoalProgressCard: View {
    let percent: Double
    let remaining: Double
    let start: Double
    let current: Double
    let goal: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Ziel-Fortschritt").font(.headline)
                Spacer()
                Text(String(format: "%.1f %%", percent))
                    .font(.title2.bold())
                    .foregroundStyle(.purple)
            }

            // Fortschrittsbalken mit Meilensteinen
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.secondary.opacity(0.2)).frame(height: 18)
                    Capsule()
                        .fill(LinearGradient(colors: [.purple, .blue],
                                             startPoint: .leading, endPoint: .trailing))
                        .frame(width: geo.size.width * CGFloat(percent / 100), height: 18)
                        .animation(.easeOut, value: percent)

                    // 5-kg-Markierungen
                    let totalLose = start - goal
                    if totalLose > 0 {
                        ForEach(Array(stride(from: 5.0, to: totalLose, by: 5.0)), id: \.self) { milestone in
                            let ratio = milestone / totalLose
                            Rectangle()
                                .fill(.white.opacity(0.7))
                                .frame(width: 2, height: 18)
                                .offset(x: geo.size.width * CGFloat(ratio) - 1)
                        }
                    }
                }
            }
            .frame(height: 18)

            HStack {
                VStack(alignment: .leading) {
                    Text("Start").font(.caption2).foregroundStyle(.secondary)
                    Text(String(format: "%.1f kg", start)).font(.caption.bold())
                }
                Spacer()
                VStack {
                    Text("Aktuell").font(.caption2).foregroundStyle(.secondary)
                    Text(String(format: "%.1f kg", current)).font(.caption.bold()).foregroundStyle(.purple)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("Ziel").font(.caption2).foregroundStyle(.secondary)
                    Text(String(format: "%.1f kg", goal)).font(.caption.bold()).foregroundStyle(.green)
                }
            }

            if remaining > 0 {
                HStack {
                    Image(systemName: "flag.checkered")
                    Text(String(format: "Noch %.1f kg bis zum Ziel", remaining))
                }
                .font(.subheadline)
                .foregroundStyle(.green)
            } else {
                Label("Ziel erreicht! 🎉", systemImage: "trophy.fill")
                    .foregroundStyle(.yellow)
                    .font(.subheadline.bold())
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Gewichts-Chart (Apple Health)

private struct WeightChartCard: View {
    let history: [(date: Date, weight: Double)]

    private var minW: Double { history.map(\.weight).min() ?? 0 }
    private var maxW: Double { history.map(\.weight).max() ?? 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Gewichtsverlauf (Apple Health)", systemImage: "chart.xyaxis.line")
                .font(.headline)

            GeometryReader { geo in
                let w = geo.size.width
                let h = geo.size.height
                let range = maxW - minW == 0 ? 1 : maxW - minW

                ZStack {
                    // Gitterlinien
                    ForEach([0.25, 0.5, 0.75], id: \.self) { frac in
                        Path { p in
                            let y = h * frac
                            p.move(to: CGPoint(x: 0, y: y))
                            p.addLine(to: CGPoint(x: w, y: y))
                        }
                        .stroke(Color.secondary.opacity(0.2), style: StrokeStyle(lineWidth: 1, dash: [4]))
                    }

                    // Linie
                    Path { p in
                        for (i, entry) in history.enumerated() {
                            let x = w * CGFloat(i) / CGFloat(max(1, history.count - 1))
                            let y = h - h * CGFloat((entry.weight - minW) / range)
                            if i == 0 { p.move(to: CGPoint(x: x, y: y)) }
                            else { p.addLine(to: CGPoint(x: x, y: y)) }
                        }
                    }
                    .stroke(Color.purple, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))

                    // Punkte
                    ForEach(history.indices, id: \.self) { i in
                        let x = w * CGFloat(i) / CGFloat(max(1, history.count - 1))
                        let y = h - h * CGFloat((history[i].weight - minW) / range)
                        Circle()
                            .fill(Color.purple)
                            .frame(width: 6, height: 6)
                            .position(x: x, y: y)
                    }
                }
            }
            .frame(height: 120)

            HStack {
                Text(String(format: "%.1f kg", minW)).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(String(format: "%.1f kg", maxW)).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Wochen-Stats

private struct WeeklyStatsCard: View {
    @EnvironmentObject var store: DataStore

    private var last7Days: [DailyLog] {
        let start = Calendar.current.date(byAdding: .day, value: -7, to: Date()) ?? Date()
        return store.logs(for: start...Date())
    }

    private var avgPoints: Double { PointsCalculator.weeklyAverage(logs: last7Days) }

    private var change7d: Double? { store.weightChange(days: 7) }
    private var change30d: Double? { store.weightChange(days: 30) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Wochenauswertung").font(.headline)

            HStack(spacing: 0) {
                WeekStat(label: "Ø Punkte/Tag",
                         value: String(format: "%.1f", avgPoints),
                         color: .purple)
                Divider()
                WeekStat(label: "Δ 7 Tage",
                         value: change7d.map { String(format: "%+.1f kg", $0) } ?? "–",
                         color: (change7d ?? 0) <= 0 ? .green : .red)
                Divider()
                WeekStat(label: "Δ 30 Tage",
                         value: change30d.map { String(format: "%+.1f kg", $0) } ?? "–",
                         color: (change30d ?? 0) <= 0 ? .green : .red)
            }
            .frame(height: 60)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

private struct WeekStat: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value).font(.subheadline.bold()).foregroundStyle(color)
            Text(label).font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Gewichtsprotokoll

private struct WeightLogSection: View {
    let entries: [WeightEntry]
    let onDelete: (WeightEntry) -> Void
    let onEdit: (WeightEntry) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Gewichtsprotokoll").font(.headline)

            if entries.isEmpty {
                Text("Noch keine Einträge").foregroundStyle(.secondary).font(.subheadline)
            } else {
                ForEach(entries) { entry in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.date, style: .date).font(.subheadline)
                            if !entry.note.isEmpty {
                                Text(entry.note).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                        Text(String(format: "%.1f kg", entry.weight))
                            .font(.subheadline.bold())
                        if entry.fromHealthKit {
                            Image(systemName: "heart.fill").foregroundStyle(.red).font(.caption)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) { onDelete(entry) } label: {
                            Label("Löschen", systemImage: "trash")
                        }
                        Button { onEdit(entry) } label: {
                            Label("Bearbeiten", systemImage: "pencil")
                        }
                        .tint(.orange)
                    }
                }
            }
        }
    }
}

// MARK: - Gewicht hinzufügen

struct AddWeightView: View {
    @EnvironmentObject var store: DataStore
    @EnvironmentObject var health: HealthKitService
    @Environment(\.dismiss) var dismiss

    @State private var weight = 80.0
    @State private var date   = Date()
    @State private var note   = ""
    @State private var syncHealth = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Gewicht") {
                    HStack {
                        TextField("kg", value: $weight, format: .number)
                            .keyboardType(.decimalPad)
                        Text("kg").foregroundStyle(.secondary)
                    }
                }
                Section("Datum") {
                    DatePicker("", selection: $date, displayedComponents: [.date])
                        .labelsHidden()
                }
                Section("Notiz") {
                    TextField("Optional...", text: $note)
                }
                if health.isAuthorized {
                    Section {
                        Toggle("Mit Apple Health synchronisieren", isOn: $syncHealth)
                    }
                }
            }
            .navigationTitle("Gewicht eintragen")
            .onAppear {
                weight = store.userProfile?.currentWeight ?? 80
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { save() }
                }
            }
        }
    }

    private func save() {
        let entry = WeightEntry(date: date, weight: weight, note: note, fromHealthKit: false)
        store.addWeight(entry)
        if syncHealth && health.isAuthorized {
            health.saveWeight(weight, date: date)
        }
        dismiss()
    }
}

// MARK: - Gewicht bearbeiten

struct EditWeightView: View {
    @EnvironmentObject var store: DataStore
    @EnvironmentObject var health: HealthKitService
    @Environment(\.dismiss) var dismiss

    @State var entry: WeightEntry

    var body: some View {
        NavigationStack {
            Form {
                Section("Gewicht") {
                    HStack {
                        TextField("kg", value: $entry.weight, format: .number)
                            .keyboardType(.decimalPad)
                        Text("kg").foregroundStyle(.secondary)
                    }
                }
                Section("Datum") {
                    DatePicker("", selection: $entry.date, displayedComponents: [.date])
                        .labelsHidden()
                }
                Section("Notiz") {
                    TextField("Optional...", text: $entry.note)
                }
            }
            .navigationTitle("Eintrag bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        store.updateWeight(entry)
                        dismiss()
                    }
                }
            }
        }
    }
}

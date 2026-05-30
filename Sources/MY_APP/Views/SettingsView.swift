import SwiftUI

// MARK: - Einstellungen

struct SettingsView: View {
    @EnvironmentObject var store: DataStore
    @EnvironmentObject var health: HealthKitService
    @State private var showEditProfile = false
    @State private var showResetAlert  = false

    private var profile: UserProfile { store.userProfile ?? UserProfile() }

    private var dailyPoints: Int {
        PointsCalculator.dailyPoints(for: profile)
    }

    var body: some View {
        NavigationStack {
            Form {
                // ── Profil ──────────────────────────────────────────────────
                Section("Mein Profil") {
                    HStack {
                        Image(systemName: "person.circle.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(.purple)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(profile.name.isEmpty ? "Mein Profil" : profile.name)
                                .font(.headline)
                            Text(profile.plan.emoji + " " + profile.plan.rawValue)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Bearbeiten") { showEditProfile = true }
                            .font(.caption)
                    }
                }

                // ── Tagespunkte ──────────────────────────────────────────────
                Section("Meine Punkte") {
                    LabeledContent("Tagespunkte", value: "\(dailyPoints)")
                    LabeledContent("Wochenpunkte", value: "\(PointsCalculator.weeklyPoints(for: profile))")
                    LabeledContent("Plan", value: profile.plan.rawValue)

                    NavigationLink("Punkte-Berechnung anzeigen") {
                        PointsBreakdownView(profile: profile)
                    }
                }

                // ── Körperdaten ──────────────────────────────────────────────
                Section("Körperdaten") {
                    LabeledContent("Startgewicht", value: String(format: "%.1f kg", profile.startWeight))
                    LabeledContent("Aktuelles Gewicht", value: String(format: "%.1f kg", profile.currentWeight))
                    LabeledContent("Zielgewicht", value: String(format: "%.1f kg", profile.goalWeight))
                    LabeledContent("Körpergröße", value: "\(Int(profile.height)) cm")
                }

                // ── Apple Health ─────────────────────────────────────────────
                Section("Apple Health") {
                    if health.isAvailable {
                        HStack {
                            Label("HealthKit", systemImage: "heart.fill")
                                .foregroundStyle(.red)
                            Spacer()
                            Text(health.isAuthorized ? "Verbunden ✅" : "Nicht verbunden")
                                .foregroundStyle(health.isAuthorized ? .green : .secondary)
                        }
                        if !health.isAuthorized {
                            Button("Zugriff anfragen") {
                                health.requestAuthorization()
                            }
                        } else {
                            Button("Daten aktualisieren") {
                                health.fetchAll()
                            }
                        }
                    } else {
                        Label("HealthKit nicht verfügbar", systemImage: "heart.slash")
                            .foregroundStyle(.secondary)
                    }
                }

                // ── App-Infos ────────────────────────────────────────────────
                Section("App") {
                    LabeledContent("Version", value: "1.0")
                    NavigationLink("0-Punkte-Lebensmittel") {
                        ZeroPointsInfoView(plan: profile.plan)
                    }
                }

                // ── Gefährliche Zone ─────────────────────────────────────────
                Section {
                    Button(role: .destructive) { showResetAlert = true } label: {
                        Label("App zurücksetzen", systemImage: "trash")
                    }
                } footer: {
                    Text("Löscht alle Daten und startet das Onboarding neu.")
                }
            }
            .navigationTitle("Einstellungen")
            .sheet(isPresented: $showEditProfile) {
                EditProfileView(profile: profile)
            }
            .alert("App zurücksetzen?", isPresented: $showResetAlert) {
                Button("Zurücksetzen", role: .destructive) { store.deleteProfile() }
                Button("Abbrechen", role: .cancel) { }
            } message: {
                Text("Alle Daten (Gewicht, Protokolle, Rezepte) werden gelöscht. Dies kann nicht rückgängig gemacht werden.")
            }
        }
    }
}

// MARK: - Punkte-Aufschlüsselung

struct PointsBreakdownView: View {
    let profile: UserProfile

    private var items: [(String, Int)] {
        var list: [(String, Int)] = []
        list.append(("Basis (\(profile.gender.rawValue))", profile.gender.basePoints))

        let age = profile.age
        let agePoints: Int
        switch age {
        case 18...20: agePoints = 5
        case 21...35: agePoints = 4
        case 36...50: agePoints = 3
        case 51...65: agePoints = 2
        default: agePoints = age >= 66 ? 1 : 0
        }
        list.append(("Alter (\(age) Jahre)", agePoints))
        list.append(("Größe (\(Int(profile.height)) cm)", profile.height < 160 ? 1 : 2))
        list.append(("Gewicht (\(Int(profile.currentWeight)) kg)", Int(profile.currentWeight / 10)))
        list.append(("Aktivität (\(profile.activityLevel.rawValue))", profile.activityLevel.points))
        list.append(("Ziel (\(profile.weightGoal.rawValue))", profile.weightGoal.points))
        return list
    }

    var body: some View {
        List {
            ForEach(items, id: \.0) { label, pts in
                HStack {
                    Text(label)
                    Spacer()
                    Text("+\(pts)").foregroundStyle(.purple).bold()
                }
            }
            Section {
                HStack {
                    Text("Gesamt").font(.headline)
                    Spacer()
                    Text("\(PointsCalculator.dailyPoints(for: profile))")
                        .font(.title2.bold())
                        .foregroundStyle(.purple)
                }
            }
        }
        .navigationTitle("Punkte-Berechnung")
    }
}

// MARK: - ZeroPoints Info

struct ZeroPointsInfoView: View {
    let plan: UserProfile.PunktePlan

    private var zeroFoods: [FoodItem] {
        PreloadedFoods.all.filter { $0.isZeroPoint(for: plan) }
    }

    var body: some View {
        List {
            Section("0-Punkte – \(plan.rawValue)") {
                ForEach(zeroFoods) { item in
                    Label(item.name, systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                }
            }
        }
        .navigationTitle("0-Punkte \(plan.emoji)")
    }
}

// MARK: - Profil bearbeiten

struct EditProfileView: View {
    @EnvironmentObject var store: DataStore
    @Environment(\.dismiss) var dismiss
    @State var profile: UserProfile

    var body: some View {
        NavigationStack {
            Form {
                Section("Name") {
                    TextField("Vorname", text: $profile.name)
                }
                Section("Plan") {
                    Picker("Plan", selection: $profile.plan) {
                        ForEach(UserProfile.PunktePlan.allCases, id: \.self) { p in
                            Text(p.emoji + " " + p.rawValue).tag(p)
                        }
                    }
                }
                Section("Aktivität") {
                    Picker("Aktivitätslevel", selection: $profile.activityLevel) {
                        ForEach(UserProfile.ActivityLevel.allCases, id: \.self) { l in
                            Text(l.emoji + " " + l.rawValue).tag(l)
                        }
                    }
                }
                Section("Ziel") {
                    Picker("Ziel", selection: $profile.weightGoal) {
                        ForEach(UserProfile.WeightGoal.allCases, id: \.self) { g in
                            Text(g.rawValue).tag(g)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                Section("Körperdaten") {
                    HStack {
                        Text("Größe")
                        Spacer()
                        TextField("cm", value: $profile.height, format: .number)
                            .keyboardType(.decimalPad).frame(width: 70).multilineTextAlignment(.trailing)
                        Text("cm").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("Zielgewicht")
                        Spacer()
                        TextField("kg", value: $profile.goalWeight, format: .number)
                            .keyboardType(.decimalPad).frame(width: 70).multilineTextAlignment(.trailing)
                        Text("kg").foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Profil bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        store.saveProfile(profile)
                        dismiss()
                    }
                }
            }
        }
    }
}

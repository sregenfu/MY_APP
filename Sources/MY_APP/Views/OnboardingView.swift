import SwiftUI

// MARK: - Onboarding (mehrstufig)

struct OnboardingView: View {
    @EnvironmentObject var store: DataStore
    @State private var step: Int = 0
    @State private var profile = UserProfile()

    var body: some View {
        NavigationStack {
            Group {
                switch step {
                case 0: WelcomeStep(step: $step)
                case 1: PersonalDataStep(profile: $profile, step: $step)
                case 2: BodyDataStep(profile: $profile, step: $step)
                case 3: ActivityGoalStep(profile: $profile, step: $step)
                case 4: PlanSelectionStep(profile: $profile, step: $step, store: store)
                default: EmptyView()
                }
            }
            .animation(.easeInOut, value: step)
        }
    }
}

// ─── Schritt 0: Willkommen ───────────────────────────────────────────────────

private struct WelcomeStep: View {
    @Binding var step: Int

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "star.circle.fill")
                .resizable()
                .scaledToFit()
                .frame(width: 100)
                .foregroundStyle(.purple)

            Text("Willkommen bei\nMY_APP")
                .font(.largeTitle).bold()
                .multilineTextAlignment(.center)

            Text("Deine persönliche Punkte-App.\nErrechne deine Tagespunkte, logge Mahlzeiten\nund verfolge deinen Fortschritt.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            Spacer()

            Button(action: { step = 1 }) {
                Label("Loslegen", systemImage: "arrow.right.circle.fill")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(.purple)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
            .padding(.horizontal)
        }
        .padding()
    }
}

// ─── Schritt 1: Persönliche Daten ────────────────────────────────────────────

private struct PersonalDataStep: View {
    @Binding var profile: UserProfile
    @Binding var step: Int

    var body: some View {
        Form {
            Section("Dein Name") {
                TextField("Vorname", text: $profile.name)
            }

            Section("Geschlecht") {
                Picker("Geschlecht", selection: $profile.gender) {
                    ForEach(UserProfile.Gender.allCases, id: \.self) { g in
                        Text(g.rawValue).tag(g)
                    }
                }
                .pickerStyle(.segmented)
            }

            Section("Geburtsdatum") {
                DatePicker("Geburtsdatum", selection: $profile.birthDate,
                           in: ...Date(), displayedComponents: .date)
                    .datePickerStyle(.compact)
            }
        }
        .navigationTitle("Über dich")
        .toolbar { nextButton { step = 2 } }
    }
}

// ─── Schritt 2: Körperdaten ────────────────────────────────────────────────

private struct BodyDataStep: View {
    @Binding var profile: UserProfile
    @Binding var step: Int

    var body: some View {
        Form {
            Section("Körpergröße (cm)") {
                Slider(value: $profile.height, in: 140...220, step: 1) {
                    Text("Größe")
                } minimumValueLabel: {
                    Text("140")
                } maximumValueLabel: {
                    Text("220")
                }
                Text("\(Int(profile.height)) cm")
                    .frame(maxWidth: .infinity, alignment: .center)
                    .font(.title2.bold())
                    .foregroundStyle(.purple)
            }

            Section("Startgewicht (kg)") {
                HStack {
                    Text("Gewicht")
                    Spacer()
                    TextField("kg", value: $profile.startWeight, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                    Text("kg").foregroundStyle(.secondary)
                }
                .onChange(of: profile.startWeight) { _, val in
                    profile.currentWeight = val
                }
            }

            Section("Zielgewicht (kg)") {
                HStack {
                    Text("Ziel")
                    Spacer()
                    TextField("kg", value: $profile.goalWeight, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                    Text("kg").foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Körperdaten")
        .toolbar { nextButton { step = 3 } }
    }
}

// ─── Schritt 3: Aktivität & Ziel ──────────────────────────────────────────

private struct ActivityGoalStep: View {
    @Binding var profile: UserProfile
    @Binding var step: Int

    var body: some View {
        Form {
            Section("Aktivitätslevel") {
                ForEach(UserProfile.ActivityLevel.allCases, id: \.self) { level in
                    HStack {
                        Text(level.emoji)
                        Text(level.rawValue)
                        Spacer()
                        if profile.activityLevel == level {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(.purple)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture { profile.activityLevel = level }
                }
            }

            Section("Dein Ziel") {
                ForEach(UserProfile.WeightGoal.allCases, id: \.self) { goal in
                    HStack {
                        Text(goal.rawValue)
                        Spacer()
                        if profile.weightGoal == goal {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(.purple)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture { profile.weightGoal = goal }
                }
            }
        }
        .navigationTitle("Aktivität & Ziel")
        .toolbar { nextButton { step = 4 } }
    }
}

// ─── Schritt 4: Plan wählen ──────────────────────────────────────────────

private struct PlanSelectionStep: View {
    @Binding var profile: UserProfile
    @Binding var step: Int
    let store: DataStore

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                Text("Wähle deinen Plan")
                    .font(.title2.bold())
                    .padding(.top)

                ForEach(UserProfile.PunktePlan.allCases, id: \.self) { plan in
                    PlanCard(plan: plan, isSelected: profile.plan == plan)
                        .onTapGesture { profile.plan = plan }
                }

                // Punktevorschau
                VStack(spacing: 8) {
                    Text("Deine täglichen Punkte")
                        .font(.headline)
                    Text("\(PointsCalculator.dailyPoints(for: profile))")
                        .font(.system(size: 56, weight: .bold))
                        .foregroundStyle(.purple)
                    Text("Punkte / Tag")
                        .foregroundStyle(.secondary)
                }
                .padding()
                .background(.purple.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .padding(.horizontal)

                Button(action: finishOnboarding) {
                    Label("App starten", systemImage: "checkmark.circle.fill")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(.purple)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .padding(.horizontal)
                .padding(.bottom)
            }
        }
        .navigationTitle("Dein Plan")
    }

    private func finishOnboarding() {
        var p = profile
        p.isOnboarded = true
        store.saveProfile(p)
        // Startgewicht als ersten Eintrag speichern
        store.addWeight(WeightEntry(date: Date(), weight: p.startWeight, note: "Startgewicht"))
    }
}

private struct PlanCard: View {
    let plan: UserProfile.PunktePlan
    let isSelected: Bool

    private var planColor: Color {
        switch plan {
        case .green:  return .green
        case .blue:   return .blue
        case .purple: return .purple
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(plan.emoji + " " + plan.rawValue)
                    .font(.headline)
                Spacer()
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(planColor)
                }
            }
            Text(plan.planDescription)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Text("0-Punkte-Lebensmittel: \(plan.zeroPointsDescription)")
                .font(.caption)
                .foregroundStyle(planColor)
        }
        .padding()
        .background(isSelected ? planColor.opacity(0.15) : Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay {
            if isSelected {
                RoundedRectangle(cornerRadius: 14)
                    .strokeBorder(planColor, lineWidth: 2)
            }
        }
        .padding(.horizontal)
    }
}

// ─── Hilfs-Toolbar-Button ────────────────────────────────────────────────────

@ToolbarContentBuilder
private func nextButton(action: @escaping () -> Void) -> some ToolbarContent {
    ToolbarItem(placement: .confirmationAction) {
        Button("Weiter", action: action)
    }
}

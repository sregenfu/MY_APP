import Foundation

struct UserProfile: Identifiable, Codable {
    var id: UUID = UUID()
    var name: String = ""
    var gender: Gender = .female
    var birthDate: Date = Calendar.current.date(byAdding: .year, value: -30, to: Date()) ?? Date()
    var height: Double = 170.0      // cm
    var startWeight: Double = 80.0  // kg
    var currentWeight: Double = 80.0
    var goalWeight: Double = 70.0
    var activityLevel: ActivityLevel = .little
    var weightGoal: WeightGoal = .lose
    var plan: PunktePlan = .balanced
    var isOnboarded: Bool = false

    init() {}

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case gender
        case birthDate
        case height
        case startWeight
        case currentWeight
        case goalWeight
        case activityLevel
        case weightGoal
        case plan
        case wwPlan
        case isOnboarded
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        id = try container.decodeIfPresent(UUID.self, forKey: .id) ?? UUID()
        name = try container.decodeIfPresent(String.self, forKey: .name) ?? ""
        gender = try container.decodeIfPresent(Gender.self, forKey: .gender) ?? .female
        birthDate = try container.decodeIfPresent(Date.self, forKey: .birthDate)
            ?? (Calendar.current.date(byAdding: .year, value: -30, to: Date()) ?? Date())
        height = try container.decodeIfPresent(Double.self, forKey: .height) ?? 170.0
        startWeight = try container.decodeIfPresent(Double.self, forKey: .startWeight) ?? 80.0
        currentWeight = try container.decodeIfPresent(Double.self, forKey: .currentWeight) ?? 80.0
        goalWeight = try container.decodeIfPresent(Double.self, forKey: .goalWeight) ?? 70.0
        activityLevel = try container.decodeIfPresent(ActivityLevel.self, forKey: .activityLevel) ?? .little
        weightGoal = try container.decodeIfPresent(WeightGoal.self, forKey: .weightGoal) ?? .lose
        plan = try container.decodeIfPresent(PunktePlan.self, forKey: .plan)
            ?? container.decodeIfPresent(PunktePlan.self, forKey: .wwPlan)
            ?? .balanced
        isOnboarded = try container.decodeIfPresent(Bool.self, forKey: .isOnboarded) ?? false
    }

    // MARK: - Enums

    enum Gender: String, Codable, CaseIterable {
        case female = "Weiblich"
        case male   = "Männlich"

        var basePoints: Int {
            switch self {
            case .female: return 7
            case .male:   return 15
            }
        }
    }

    enum ActivityLevel: String, Codable, CaseIterable {
        case none     = "Kaum Bewegung"
        case little   = "Wenig Bewegung"
        case moderate = "Viel Bewegung"
        case high     = "Täglich viel Bewegung"

        var points: Int {
            switch self {
            case .none:     return 0
            case .little:   return 2
            case .moderate: return 4
            case .high:     return 6
            }
        }

        var icon: String {
            switch self {
            case .none:     return "🛋️"
            case .little:   return "🚶"
            case .moderate: return "🏃"
            case .high:     return "🏋️"
            }
        }
    }

    enum WeightGoal: String, Codable, CaseIterable {
        case maintain = "Gewicht halten"
        case lose     = "Abnehmen"

        var points: Int {
            switch self {
            case .maintain: return 4
            case .lose:     return 0
            }
        }
    }

    enum PunktePlan: String, Codable, CaseIterable {
        case restricted = "Restriktiv"
        case balanced   = "Ausgewogen"
        case liberal    = "Liberal"

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            let raw = ((try? container.decode(String.self)) ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .lowercased()

            switch raw {
            case "restriktiv", "restricted", "rot", "red":
                self = .restricted
            case "ausgewogen", "balanced", "blau", "blue", "":
                self = .balanced
            case "liberal", "gruen", "grün", "green":
                self = .liberal
            default:
                self = .balanced
            }
        }

        func encode(to encoder: Encoder) throws {
            var container = encoder.singleValueContainer()
            try container.encode(rawValue)
        }

        var planDescription: String {
            switch self {
            case .restricted: return "Höchste Tagespunkte – weniger Zero-Punkte"
            case .balanced:   return "Ausgewogen – mittlere Menge Zero-Punkte"
            case .liberal:    return "Niedrigste Tagespunkte – viele Zero-Punkte-Lebensmittel"
            }
        }

        var colorName: String {
            switch self {
            case .restricted: return "red"
            case .balanced:   return "blue"
            case .liberal:    return "green"
            }
        }

        var emoji: String {
            switch self {
            case .restricted: return "🔴"
            case .balanced:   return "🔵"
            case .liberal:    return "🟢"
            }
        }

        var zeroPointsDescription: String {
            switch self {
            case .restricted:
                return "Obst, Gemüse"
            case .balanced:
                return "Obst, Gemüse, Hülsenfrüchte, Eier, mageres Fleisch"
            case .liberal:
                return "Obst, Gemüse, Vollkornprodukte, Fisch, Kartoffeln, Eier"
            }
        }
    }

    // MARK: - Computed

    var age: Int {
        Calendar.current.dateComponents([.year], from: birthDate, to: Date()).year ?? 30
    }
}

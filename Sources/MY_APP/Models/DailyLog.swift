import Foundation

// MARK: - Gewichtseintrag

struct WeightEntry: Identifiable, Codable {
    var id: UUID    = UUID()
    var date: Date
    var weight: Double  // kg
    var note: String    = ""
    var fromHealthKit: Bool = false
}

// MARK: - Mahlzeit-Typ

enum MealType: String, Codable, CaseIterable {
    case breakfast = "Frühstück"
    case lunch     = "Mittagessen"
    case dinner    = "Abendessen"
    case snack     = "Snack"

    var emoji: String {
        switch self {
        case .breakfast: return "☀️"
        case .lunch:     return "🌤️"
        case .dinner:    return "🌙"
        case .snack:     return "🍏"
        }
    }
}

// MARK: - Geloggtes Lebensmittel

struct LoggedFood: Identifiable, Codable {
    var id: UUID             = UUID()
    var foodItemId: UUID?
    var recipeId: UUID?
    var name: String
    var amount: Double       // Gramm
    var points: Double
    var mealType: MealType   = .snack
    var time: Date           = Date()
}

// MARK: - Tagesprotokoll

struct DailyLog: Identifiable, Codable {
    var id: UUID                  = UUID()
    var date: Date
    var loggedFoods: [LoggedFood] = []
    var bonusActivityPoints: Int  = 0   // manuell hinzugefügte Aktivitätspunkte
    var waterIntake: Double       = 0.0 // Liter
    var note: String              = ""

    var totalPointsUsed: Double {
        loggedFoods.reduce(0) { $0 + $1.points }
    }

    var dateKey: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        return fmt.string(from: date)
    }
}

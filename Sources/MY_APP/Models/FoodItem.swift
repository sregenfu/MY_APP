import Foundation

// MARK: - Kategorie

enum FoodCategory: String, Codable, CaseIterable, Identifiable {
    case bread       = "Brot & Teigwaren"
    case spread      = "Brotaufstriche"
    case dessert     = "Desserts"
    case meat        = "Fleisch & Wurst"
    case poultry     = "Geflügel"
    case fish        = "Fisch"
    case dairy       = "Milch & Milchprodukte"
    case cheese      = "Käse"
    case fatsOils    = "Fette & Öle"
    case potatoes    = "Kartoffeln"
    case pasta       = "Nudeln"
    case grains      = "Getreideprodukte"
    case fruit       = "Obst"
    case vegetables  = "Gemüse"
    case legumes     = "Hülsenfrüchte"
    case eggs        = "Eier"
    case drinks      = "Getränke"
    case snacks      = "Snacks"
    case other       = "Sonstiges"
    case custom      = "Eigene Lebensmittel"

    var id: String { rawValue }

    var emoji: String {
        switch self {
        case .bread:      return "🍞"
        case .spread:     return "🍯"
        case .dessert:    return "🍰"
        case .meat:       return "🥩"
        case .poultry:    return "🍗"
        case .fish:       return "🐟"
        case .dairy:      return "🥛"
        case .cheese:     return "🧀"
        case .fatsOils:   return "🫙"
        case .potatoes:   return "🥔"
        case .pasta:      return "🍝"
        case .grains:     return "🌾"
        case .fruit:      return "🍎"
        case .vegetables: return "🥦"
        case .legumes:    return "🫘"
        case .eggs:       return "🥚"
        case .drinks:     return "🥤"
        case .snacks:     return "🍿"
        case .other:      return "🍽️"
        case .custom:     return "✏️"
        }
    }
}

// MARK: - Lebensmittel

struct FoodItem: Identifiable, Codable {
    var id: UUID             = UUID()
    var name: String
    var category: FoodCategory
    var portionSize: Double           // Gramm / ml
    var portionDescription: String    // z. B. "1 Scheibe (30 g)"
    var kcal: Double
    var fat: Double                   // g
    var saturatedFat: Double          // g
    var carbs: Double                 // g
    var sugar: Double                 // g
    var protein: Double               // g
    var fiber: Double                 // g
    var punkteValue: Double           // berechnete Punkte
    var isZeroPointRestricted: Bool = false
    var isZeroPointBalanced: Bool    = false
    var isZeroPointLiberal: Bool     = false
    var isCustom: Bool          = false

    // Punkte je nach aktivem Plan
    func points(for plan: UserProfile.PunktePlan) -> Double {
        switch plan {
        case .restricted: return isZeroPointRestricted ? 0 : punkteValue
        case .balanced:   return isZeroPointBalanced   ? 0 : punkteValue
        case .liberal:    return isZeroPointLiberal    ? 0 : punkteValue
        }
    }

    func isZeroPoint(for plan: UserProfile.PunktePlan) -> Bool {
        return points(for: plan) == 0
    }
}

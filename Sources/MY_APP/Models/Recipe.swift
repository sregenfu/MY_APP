import Foundation

// MARK: - Zutat

struct RecipeIngredient: Identifiable, Codable {
    var id: UUID            = UUID()
    var foodItemId: UUID
    var foodItemName: String
    var amount: Double      // Gramm
    var points: Double      // Punkte für diese Menge
}

// MARK: - Rezept

struct Recipe: Identifiable, Codable {
    var id: UUID                         = UUID()
    var name: String
    var category: FoodCategory           = .other
    var servings: Int                    = 2
    var ingredients: [RecipeIngredient]  = []
    var instructions: String             = ""
    var createdAt: Date                  = Date()
    var isCustom: Bool                   = true

    // Gesamtpunkte aller Zutaten
    var totalPoints: Double {
        ingredients.reduce(0) { $0 + $1.points }
    }

    // Punkte pro Portion
    var pointsPerServing: Double {
        guard servings > 0 else { return totalPoints }
        return totalPoints / Double(servings)
    }

    // Gesamtkalorien (geschätzt aus Zutaten)
    var totalKcal: Double = 0
    var kcalPerServing: Double {
        guard servings > 0 else { return totalKcal }
        return totalKcal / Double(servings)
    }
}

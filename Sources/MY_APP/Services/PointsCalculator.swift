import Foundation

// MARK: - Punkterechner

struct PointsCalculator {

    // MARK: Tagespunkte

    static func dailyPoints(for profile: UserProfile) -> Int {
        var points = 0

        // 1. Basis: Geschlecht
        points += profile.gender.basePoints

        // 2. Alter
        let age = profile.age
        switch age {
        case 18...20: points += 5
        case 21...35: points += 4
        case 36...50: points += 3
        case 51...65: points += 2
        default:
            if age >= 66 { points += 1 }
        }

        // 3. Körpergröße
        points += profile.height < 160 ? 1 : 2

        // 4. Gewicht (1/10 des Gewichts, abgerundet)
        points += Int(profile.currentWeight / 10)

        // 5. Aktivitätslevel
        points += profile.activityLevel.points

        // 6. Ziel
        points += profile.weightGoal.points

        return max(18, points) // Mindestens 18 Punkte
    }

    // MARK: Punkte-Berechnung
    // Basis: kcal, gesättigte Fettsäuren, Zucker, Protein

    static func calculatePoints(kcal: Double,
                            fat: Double,
                            saturatedFat: Double? = nil,
                            sugar: Double,
                            protein: Double) -> Double {
        let satFat = saturatedFat ?? (fat * 0.4)
        let raw = kcal * 0.0305 + satFat * 0.275 + sugar * 0.12 - protein * 0.098
        let rounded = (raw * 2).rounded() / 2  // auf 0.5 runden
        return max(0, rounded)
    }

    // MARK: Wochenpunkte (7× täglich + 35 Bonuspunkte)

    static func weeklyPoints(for profile: UserProfile) -> Int {
        return dailyPoints(for: profile) * 7 + 35
    }

    // MARK: Fortschritt & Meilensteine

    static func starsEarned(startWeight: Double, currentWeight: Double) -> Int {
        let lost = startWeight - currentWeight
        return max(0, Int(lost / 5))
    }

    static func nextMilestone(startWeight: Double, currentWeight: Double) -> Double {
        let lost = startWeight - currentWeight
        let nextStep = (floor(lost / 5) + 1) * 5
        return startWeight - nextStep
    }

    static func kgToNextMilestone(startWeight: Double, currentWeight: Double) -> Double {
        let lost = startWeight - currentWeight
        let next = (floor(lost / 5) + 1) * 5
        return max(0, next - lost)
    }

    static func percentToGoal(startWeight: Double, currentWeight: Double, goalWeight: Double) -> Double {
        let totalToLose = startWeight - goalWeight
        guard totalToLose > 0 else { return 100 }
        let lost = startWeight - currentWeight
        return min(100, max(0, (lost / totalToLose) * 100))
    }

    static func remainingToGoal(currentWeight: Double, goalWeight: Double) -> Double {
        return max(0, currentWeight - goalWeight)
    }

    // MARK: Wochenauswertung

    static func weeklyAverage(logs: [DailyLog]) -> Double {
        guard !logs.isEmpty else { return 0 }
        let total = logs.reduce(0.0) { $0 + $1.totalPointsUsed }
        return total / Double(logs.count)
    }

    static func bestWeek(weightEntries: [WeightEntry]) -> (start: Double, end: Double, lost: Double)? {
        guard weightEntries.count >= 2 else { return nil }
        var bestLoss: Double = 0
        var bestResult: (Double, Double, Double)? = nil
        let sorted = weightEntries.sorted { $0.date < $1.date }
        for i in 1..<sorted.count {
            let diff = sorted[i - 1].weight - sorted[i].weight
            if diff > bestLoss {
                bestLoss = diff
                bestResult = (sorted[i - 1].weight, sorted[i].weight, diff)
            }
        }
        return bestResult
    }
}

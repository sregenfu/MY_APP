import Foundation
import Combine

// MARK: - Datenspeicher

class DataStore: ObservableObject {

    // MARK: Published State

    @Published var userProfile: UserProfile? = nil
    @Published var foodItems: [FoodItem]     = []
    @Published var recipes: [Recipe]         = []
    @Published var weightEntries: [WeightEntry] = []
    @Published var dailyLogs: [DailyLog]     = []

    // MARK: Keys

    private let profileKey      = "myapp_userProfile"
    private let customFoodsKey  = "myapp_customFoods"
    private let recipesKey      = "myapp_recipes"
    private let weightsKey      = "myapp_weightEntries"
    private let logsKey         = "myapp_dailyLogs"

    private let legacyProfileKey     = "ww_userProfile"
    private let legacyCustomFoodsKey = "ww_customFoods"
    private let legacyRecipesKey     = "ww_recipes"
    private let legacyWeightsKey     = "ww_weightEntries"
    private let legacyLogsKey        = "ww_dailyLogs"

    private let defaults = UserDefaults.standard

    // MARK: Init

    init() {
        loadAll()
        // Vorgeladene Lebensmittel immer ergänzen
        let preloaded = PreloadedFoods.all
        let custom    = loadCustomFoods()
        foodItems     = preloaded + custom
    }

    // MARK: Laden

    private func loadAll() {
        userProfile    = loadWithLegacy(newKey: profileKey, legacyKey: legacyProfileKey)
        weightEntries  = loadWithLegacy(newKey: weightsKey, legacyKey: legacyWeightsKey) ?? []
        dailyLogs      = loadWithLegacy(newKey: logsKey, legacyKey: legacyLogsKey) ?? []
        recipes        = loadWithLegacy(newKey: recipesKey, legacyKey: legacyRecipesKey) ?? []
    }

    private func loadCustomFoods() -> [FoodItem] {
        return loadWithLegacy(newKey: customFoodsKey, legacyKey: legacyCustomFoodsKey) ?? []
    }

    private func load<T: Decodable>(key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private func save<T: Encodable>(_ value: T, key: String) {
        if let data = try? JSONEncoder().encode(value) {
            defaults.set(data, forKey: key)
        }
    }

    private func loadWithLegacy<T: Codable>(newKey: String, legacyKey: String) -> T? {
        if let current: T = load(key: newKey) {
            return current
        }
        guard let legacy: T = load(key: legacyKey) else { return nil }

        // One-time migration: persist legacy value under the new neutral key.
        save(legacy, key: newKey)
        return legacy
    }

    // MARK: Benutzerprofil

    func saveProfile(_ profile: UserProfile) {
        userProfile = profile
        save(profile, key: profileKey)
    }

    func deleteProfile() {
        userProfile = nil
        defaults.removeObject(forKey: profileKey)
        defaults.removeObject(forKey: legacyProfileKey)
    }

    // MARK: Lebensmittel

    var customFoods: [FoodItem] { foodItems.filter { $0.isCustom } }

    func addFood(_ item: FoodItem) {
        var f = item
        f.isCustom = true
        foodItems.append(f)
        saveCustomFoods()
    }

    func updateFood(_ item: FoodItem) {
        if let idx = foodItems.firstIndex(where: { $0.id == item.id }) {
            foodItems[idx] = item
            saveCustomFoods()
        }
    }

    func deleteFood(_ item: FoodItem) {
        foodItems.removeAll { $0.id == item.id }
        saveCustomFoods()
    }

    private func saveCustomFoods() {
        let custom = foodItems.filter { $0.isCustom }
        save(custom, key: customFoodsKey)
    }

    func food(by id: UUID) -> FoodItem? {
        foodItems.first { $0.id == id }
    }

    // MARK: Rezepte

    func addRecipe(_ recipe: Recipe) {
        recipes.append(recipe)
        save(recipes, key: recipesKey)
    }

    func updateRecipe(_ recipe: Recipe) {
        if let idx = recipes.firstIndex(where: { $0.id == recipe.id }) {
            recipes[idx] = recipe
            save(recipes, key: recipesKey)
        }
    }

    func deleteRecipe(_ recipe: Recipe) {
        recipes.removeAll { $0.id == recipe.id }
        save(recipes, key: recipesKey)
    }

    // MARK: Gewicht

    func addWeight(_ entry: WeightEntry) {
        weightEntries.append(entry)
        weightEntries.sort { $0.date > $1.date }
        save(weightEntries, key: weightsKey)
        // Aktuelles Gewicht im Profil aktualisieren
        if var profile = userProfile {
            profile.currentWeight = entry.weight
            saveProfile(profile)
        }
    }

    func updateWeight(_ entry: WeightEntry) {
        if let idx = weightEntries.firstIndex(where: { $0.id == entry.id }) {
            weightEntries[idx] = entry
            save(weightEntries, key: weightsKey)
        }
    }

    func deleteWeight(_ entry: WeightEntry) {
        weightEntries.removeAll { $0.id == entry.id }
        save(weightEntries, key: weightsKey)
    }

    var latestWeight: Double? {
        weightEntries.sorted { $0.date > $1.date }.first?.weight
    }

    // MARK: Tagesprotokoll

    func log(for date: Date) -> DailyLog? {
        let key = dateKey(date)
        return dailyLogs.first { $0.dateKey == key }
    }

    func logOrCreate(for date: Date) -> DailyLog {
        if let existing = log(for: date) { return existing }
        let newLog = DailyLog(date: date)
        dailyLogs.append(newLog)
        return newLog
    }

    func addFood(_ food: LoggedFood, to date: Date) {
        let key = dateKey(date)
        if let idx = dailyLogs.firstIndex(where: { $0.dateKey == key }) {
            dailyLogs[idx].loggedFoods.append(food)
        } else {
            var log = DailyLog(date: date)
            log.loggedFoods.append(food)
            dailyLogs.append(log)
        }
        saveLogs()
    }

    func removeFood(_ food: LoggedFood, from date: Date) {
        let key = dateKey(date)
        if let idx = dailyLogs.firstIndex(where: { $0.dateKey == key }) {
            dailyLogs[idx].loggedFoods.removeAll { $0.id == food.id }
        }
        saveLogs()
    }

    func updateLog(_ log: DailyLog) {
        if let idx = dailyLogs.firstIndex(where: { $0.dateKey == log.dateKey }) {
            dailyLogs[idx] = log
        } else {
            dailyLogs.append(log)
        }
        saveLogs()
    }

    private func saveLogs() {
        save(dailyLogs, key: logsKey)
    }

    // MARK: Statistik-Helfer

    func logs(for range: ClosedRange<Date>) -> [DailyLog] {
        dailyLogs.filter { range.contains($0.date) }
    }

    func weightChange(days: Int) -> Double? {
        let sorted = weightEntries.sorted { $0.date > $1.date }
        guard sorted.count >= 2 else { return nil }
        let cutoff = Calendar.current.date(byAdding: .day, value: -days, to: Date()) ?? Date()
        let recent = sorted.filter { $0.date >= cutoff }
        guard let first = recent.last?.weight, let last = recent.first?.weight else { return nil }
        return last - first
    }

    // MARK: Privat

    private func dateKey(_ date: Date) -> String {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        return fmt.string(from: date)
    }
}

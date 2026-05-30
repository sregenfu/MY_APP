import Foundation
import HealthKit

// MARK: - HealthKit-Service

class HealthKitService: ObservableObject {

    static let shared = HealthKitService()

    private let store = HKHealthStore()

    @Published var isAuthorized: Bool    = false
    @Published var latestWeight: Double? = nil
    @Published var todaySteps: Double    = 0
    @Published var todayActiveKcal: Double = 0
    @Published var weightHistory: [(date: Date, weight: Double)] = []

    private let weightType       = HKQuantityType.quantityType(forIdentifier: .bodyMass)!
    private let stepsType        = HKQuantityType.quantityType(forIdentifier: .stepCount)!
    private let activeEnergyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned)!

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    // MARK: Autorisierung

    func requestAuthorization() {
        guard isAvailable else { return }
        let read: Set<HKObjectType>   = [weightType, stepsType, activeEnergyType]
        let write: Set<HKSampleType>  = [weightType]

        store.requestAuthorization(toShare: write, read: read) { [weak self] success, _ in
            DispatchQueue.main.async {
                self?.isAuthorized = success
                if success {
                    self?.fetchAll()
                }
            }
        }
    }

    func fetchAll() {
        fetchLatestWeight()
        fetchTodaySteps()
        fetchTodayActiveKcal()
        fetchWeightHistory(days: 90)
    }

    // MARK: Lesen

    func fetchLatestWeight() {
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: weightType, predicate: nil,
                                  limit: 1, sortDescriptors: [sort]) { [weak self] _, results, _ in
            DispatchQueue.main.async {
                if let sample = results?.first as? HKQuantitySample {
                    self?.latestWeight = sample.quantity.doubleValue(for: .gramUnit(with: .kilo))
                }
            }
        }
        store.execute(query)
    }

    func fetchTodaySteps() {
        fetchDayStat(type: stepsType, unit: .count()) { [weak self] val in
            self?.todaySteps = val
        }
    }

    func fetchTodayActiveKcal() {
        fetchDayStat(type: activeEnergyType, unit: .kilocalorie()) { [weak self] val in
            self?.todayActiveKcal = val
        }
    }

    private func fetchDayStat(type: HKQuantityType, unit: HKUnit, completion: @escaping (Double) -> Void) {
        let start = Calendar.current.startOfDay(for: Date())
        let pred  = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)
        let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: pred,
                                      options: .cumulativeSum) { _, result, _ in
            DispatchQueue.main.async {
                completion(result?.sumQuantity()?.doubleValue(for: unit) ?? 0)
            }
        }
        store.execute(query)
    }

    func fetchWeightHistory(days: Int = 90) {
        let start = Calendar.current.date(byAdding: .day, value: -days, to: Date()) ?? Date()
        let pred  = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)
        let sort  = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: true)
        let query = HKSampleQuery(sampleType: weightType, predicate: pred,
                                  limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { [weak self] _, results, _ in
            DispatchQueue.main.async {
                self?.weightHistory = (results as? [HKQuantitySample] ?? []).map {
                    (date: $0.endDate, weight: $0.quantity.doubleValue(for: .gramUnit(with: .kilo)))
                }
            }
        }
        store.execute(query)
    }

    // MARK: Schreiben

    func saveWeight(_ weight: Double, date: Date = Date(), completion: ((Bool) -> Void)? = nil) {
        guard isAuthorized else { completion?(false); return }
        let quantity = HKQuantity(unit: .gramUnit(with: .kilo), doubleValue: weight)
        let sample   = HKQuantitySample(type: weightType, quantity: quantity, start: date, end: date)
        store.save(sample) { [weak self] success, _ in
            DispatchQueue.main.async {
                if success { self?.fetchAll() }
                completion?(success)
            }
        }
    }

    // MARK: Löschen

    func deleteWeightSample(at date: Date) {
        let start = Calendar.current.startOfDay(for: date)
        let end   = Calendar.current.date(byAdding: .day, value: 1, to: start)!
        let pred  = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: weightType, predicate: pred,
                                  limit: HKObjectQueryNoLimit, sortDescriptors: nil) { [weak self] _, results, _ in
            guard let samples = results, !samples.isEmpty else { return }
            self?.store.delete(samples) { [weak self] _, _ in
                DispatchQueue.main.async { self?.fetchAll() }
            }
        }
        store.execute(query)
    }
}

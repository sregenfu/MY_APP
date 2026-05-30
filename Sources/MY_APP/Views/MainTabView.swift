import SwiftUI

// MARK: - Haupt-Tab-Navigation

struct MainTabView: View {
    @EnvironmentObject var store: DataStore
    @StateObject private var health = HealthKitService.shared

    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Heute", systemImage: "house.fill") }

            FoodDatabaseView()
                .tabItem { Label("Lebensmittel", systemImage: "fork.knife") }

            RecipesView()
                .tabItem { Label("Rezepte", systemImage: "book.fill") }

            StatisticsView()
                .tabItem { Label("Statistik", systemImage: "chart.line.uptrend.xyaxis") }

            SettingsView()
                .tabItem { Label("Einstellungen", systemImage: "gear") }
        }
        .environmentObject(health)
        .onAppear { health.requestAuthorization() }
    }
}

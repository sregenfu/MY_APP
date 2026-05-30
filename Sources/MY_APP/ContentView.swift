import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: DataStore

    var body: some View {
        Group {
            if store.userProfile?.isOnboarded == true {
                MainTabView()
            } else {
                OnboardingView()
            }
        }
    }
}

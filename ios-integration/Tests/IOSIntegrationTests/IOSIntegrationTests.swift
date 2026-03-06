import XCTest
@testable import IOSIntegration

final class IOSIntegrationTests: XCTestCase {
    func testModuleLoads() {
        // Verifies that the IOSIntegration module can be imported and
        // that the ContentView type is accessible.
        _ = ContentView()
    }
}

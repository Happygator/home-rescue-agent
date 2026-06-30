/// App configuration, sourced from compile-time defines.
///
/// DEFAULT IS PRODUCTION. A bare `flutter run -d chrome` (or any build with no
/// flag) points at the hosted Cloud Run backend, so testing needs no extra
/// args. The defaults below mirror config/prod.json.
///
/// To run against a LOCAL backend, pass the dev config file:
///   flutter run -d chrome --dart-define-from-file=config/dev.json
/// Android emulator local backend uses 10.0.2.2 instead of localhost:
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
///
/// You can also point at production explicitly (e.g. in CI) with
/// --dart-define-from-file=config/prod.json. An inline
/// --dart-define=API_BASE_URL=... always takes precedence over the defaults.
class AppConfig {
  /// Base URL of the HomeRescue backend (no trailing slash).
  /// Defaults to the hosted Cloud Run backend (see config/prod.json).
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://home-rescue-1035771619142.us-central1.run.app',
  );

  /// Environment label (e.g. 'production', 'development'). Handy for logging,
  /// diagnostics, and any environment-conditional behavior.
  static const String environment = String.fromEnvironment(
    'APP_ENV',
    defaultValue: 'production',
  );

  /// True when running against the production (hosted) backend.
  static bool get isProduction => environment == 'production';
}

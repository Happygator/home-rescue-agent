/// Backend base URL. Override at run time with:
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000   (Android emulator)
/// Defaults to localhost for web / desktop / iOS simulator.
class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
}

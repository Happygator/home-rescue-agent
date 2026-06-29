import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Anonymous, per-device user identity. No login required: on first launch we
/// mint a random UUID and persist it (browser localStorage on web, native
/// preferences elsewhere) so this device keeps the same id across runs. It is
/// sent to the backend as the `X-User-Id` header to scope issues to this device.
class DeviceId {
  static const _key = 'device_user_id';
  static String _value = '';

  /// The cached device id. Empty only until [init] has completed.
  static String get value => _value;

  /// Load the persisted id, generating and storing one on first launch.
  /// Call once during app startup, before any API request is made.
  static Future<String> init() async {
    if (_value.isNotEmpty) return _value;
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_key);
    if (id == null || id.isEmpty) {
      id = const Uuid().v4();
      await prefs.setString(_key, id);
    }
    _value = id;
    return _value;
  }
}

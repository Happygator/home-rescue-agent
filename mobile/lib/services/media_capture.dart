import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

/// Camera/photo capture with an in-context permission request. On web, permission_handler is a
/// no-op (the browser prompts), so we skip it. Returns image bytes, or null when the permission
/// was denied or the user cancelled -- callers then show the type-in / gallery fallback.
class MediaCapture {
  final ImagePicker _picker;
  MediaCapture({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  Future<bool> ensureCameraPermission() async {
    if (kIsWeb) return true;
    final status = await Permission.camera.request();
    return status.isGranted;
  }

  /// Capture a photo from the camera. null => denied/cancelled.
  Future<List<int>?> capturePhoto() async {
    if (!await ensureCameraPermission()) return null;
    final XFile? file = await _picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 1600,
      imageQuality: 85,
    );
    if (file == null) return null;
    return await file.readAsBytes();
  }

  /// Pick an existing image (gallery / file system) -- the denied-camera fallback.
  Future<List<int>?> pickFromGallery() async {
    final XFile? file = await _picker.pickImage(source: ImageSource.gallery);
    if (file == null) return null;
    return await file.readAsBytes();
  }
}

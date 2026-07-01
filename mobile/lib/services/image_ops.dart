import 'dart:typed_data';

import 'package:flutter/foundation.dart' show compute;
import 'package:image/image.dart' as img;

/// Rotate raw image bytes 90 degrees clockwise and re-encode as JPEG.
///
/// Runs the decode/rotate/encode work off the UI thread via compute(). If the
/// bytes cannot be decoded (e.g. an unsupported format) the original bytes are
/// returned unchanged so the caller still has a usable image.
Future<List<int>> rotateImage90(List<int> bytes) {
  return compute(_rotate90, bytes);
}

List<int> _rotate90(List<int> bytes) {
  final decoded = img.decodeImage(Uint8List.fromList(bytes));
  if (decoded == null) return bytes;
  final rotated = img.copyRotate(decoded, angle: 90);
  return img.encodeJpg(rotated, quality: 90);
}

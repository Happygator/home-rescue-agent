import 'dart:async';

import '../api/api_client.dart';

/// Upload media with a simple inline retry on transient failure (flaky garage Wi-Fi).
Future<String> uploadMediaWithRetry(
  ApiClient api,
  String caseId,
  List<int> bytes, {
  required String filename,
  String kind = 'symptom',
  String mime = 'image/jpeg',
  int retries = 2,
  Duration baseDelay = const Duration(milliseconds: 250),
}) async {
  var attempt = 0;
  while (true) {
    try {
      return await api.uploadMedia(caseId, bytes, filename: filename, kind: kind, mime: mime);
    } catch (_) {
      attempt++;
      if (attempt > retries) rethrow;
      await Future.delayed(baseDelay * attempt);
    }
  }
}

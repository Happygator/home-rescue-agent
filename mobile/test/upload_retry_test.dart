import 'dart:convert';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/services/upload.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const baseUrl = 'http://example.test';

  test('upload succeeds after one transient failure', () async {
    var attempts = 0;
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient.streaming((req, bodyStream) async {
        attempts++;
        if (attempts == 1) {
          return http.StreamedResponse(Stream.value(utf8.encode('err')), 500);
        }
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'ref': 'r1'}))),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    final ref = await uploadMediaWithRetry(
      client,
      'case-1',
      [1, 2, 3],
      filename: 'plate.jpg',
      retries: 2,
      baseDelay: Duration.zero,
    );

    expect(ref, 'r1');
    expect(attempts, 2);
  });

  test('upload gives up after exhausting retries', () async {
    var attempts = 0;
    final client = ApiClient(
      baseUrl: baseUrl,
      client: MockClient.streaming((req, bodyStream) async {
        attempts++;
        return http.StreamedResponse(Stream.value(utf8.encode('err')), 500);
      }),
    );

    await expectLater(
      uploadMediaWithRetry(
        client,
        'case-1',
        [1, 2, 3],
        filename: 'plate.jpg',
        retries: 1,
        baseDelay: Duration.zero,
      ),
      throwsA(isA<ApiException>()),
    );
    expect(attempts, 2);
  });
}

import 'dart:convert';

import 'package:appliance_fixer/api/api_client.dart';
import 'package:appliance_fixer/screens/new_issue_screen.dart';
import 'package:appliance_fixer/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('camera-denied manual entry offers photo fallback', (tester) async {
    final client = ApiClient(
      baseUrl: 'http://test',
      client: MockClient.streaming((req, body) async {
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'case_id': 'case-new123'}))),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    await tester.binding.setSurfaceSize(const Size(440, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: NewIssueScreen(client: client, capturePlate: () async => null),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.photo_camera_outlined));
    await tester.pumpAndSettle();

    expect(find.text('Choose from photos'), findsOneWidget);
  });
}

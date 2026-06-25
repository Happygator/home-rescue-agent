import 'dart:convert';
import 'dart:io';

import 'package:appliance_fixer/api/api_client.dart';
import 'package:appliance_fixer/screens/home_screen.dart';
import 'package:appliance_fixer/theme.dart';
import 'package:appliance_fixer/widgets/issue_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  ApiClient fixtureClient() {
    final open = File('test/fixtures/issues_list.json').readAsStringSync();
    final resolved = File('test/fixtures/issues_resolved.json').readAsStringSync();
    return ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        final body = request.url.queryParameters['status'] == 'resolved' ? resolved : open;
        return http.Response.bytes(utf8.encode(body), 200);
      }),
    );
  }

  Widget app() => MaterialApp(
        theme: buildAppTheme(),
        home: HomeScreen(client: fixtureClient()),
      );

  // A tall phone-sized surface so all cards + the footer render (a ListView does not
  // build children below the fold, which the default 800x600 test viewport would clip).
  Future<void> pumpHome(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
  }

  testWidgets('renders open issues list', (tester) async {
    await pumpHome(tester);

    expect(find.byType(IssueCard), findsNWidgets(3));
    expect(find.text('Open Issues'), findsOneWidget);
    expect(find.text('Samsung ${String.fromCharCode(0x00B7)} Refrigerator'), findsOneWidget);
    expect(find.text('Whirlpool ${String.fromCharCode(0x00B7)} Refrigerator'), findsOneWidget);
    expect(find.text('LG ${String.fromCharCode(0x00B7)} Refrigerator'), findsOneWidget);
    expect(find.text('DIAGNOSING'), findsOneWidget);
    expect(find.text('AWAITING YOU'), findsOneWidget);
    expect(find.text('ESCALATED'), findsOneWidget);
    expect(find.text('View resolved (4)'), findsOneWidget);
    expect(find.text('Door alarm kept beeping.'), findsNothing);
  });

  testWidgets('toggles to resolved issues', (tester) async {
    await pumpHome(tester);

    await tester.tap(find.text('View resolved (4)'));
    await tester.pumpAndSettle();

    expect(find.byType(IssueCard), findsNWidgets(4));
    expect(find.text('Resolved Issues'), findsOneWidget);
  });

  group('StatusStyle', () {
    test('diagnosing badge background', () {
      expect(StatusStyle.of('diagnosing').badgeBg, const Color(0xFFFEF3C7));
    });

    test('escalated dot', () {
      expect(StatusStyle.of('escalated').dot, const Color(0xFFEF4444));
    });
  });
}

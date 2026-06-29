import 'dart:convert';
import 'dart:io';

import 'package:home_rescue/api/api_client.dart';
import 'package:home_rescue/screens/home_screen.dart';
import 'package:home_rescue/theme.dart';
import 'package:home_rescue/widgets/issue_card.dart';
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

  // A client that returns no issues for either status, to exercise the empty state.
  ApiClient emptyClient() => ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async => http.Response.bytes(utf8.encode('[]'), 200)),
      );

  Widget app() => MaterialApp(
        theme: buildAppTheme(),
        home: HomeScreen(client: fixtureClient()),
      );

  Widget appWith(ApiClient client) => MaterialApp(
        theme: buildAppTheme(),
        home: HomeScreen(client: client),
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

  testWidgets('shows a blurb when there are no open issues', (tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(appWith(emptyClient()));
    await tester.pumpAndSettle();

    expect(find.byType(IssueCard), findsNothing);
    expect(find.text('No open issues'), findsOneWidget);
    expect(find.text("You're all caught up. Tap the + button to start a new repair."),
        findsOneWidget);

    // Toggling to the (also empty) resolved view swaps in the resolved blurb.
    await tester.tap(find.text('View resolved (0)'));
    await tester.pumpAndSettle();
    expect(find.text('No resolved issues yet'), findsOneWidget);
  });

  testWidgets('toggles to resolved issues', (tester) async {
    await pumpHome(tester);

    await tester.tap(find.text('View resolved (4)'));
    await tester.pumpAndSettle();

    expect(find.byType(IssueCard), findsNWidgets(4));
    expect(find.text('Resolved Issues'), findsOneWidget);
  });

  testWidgets('ticket overflow menu offers edit and delete', (tester) async {
    await pumpHome(tester);

    // Every card carries a 3-dot options button.
    expect(find.byIcon(Icons.more_vert), findsNWidgets(3));

    await tester.tap(find.byIcon(Icons.more_vert).first);
    await tester.pumpAndSettle();

    expect(find.text('Edit details'), findsOneWidget);
    expect(find.text('Delete'), findsOneWidget);
  });

  testWidgets('delete asks for confirmation before removing', (tester) async {
    await pumpHome(tester);

    await tester.tap(find.byIcon(Icons.more_vert).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();

    expect(find.text('Delete ticket?'), findsOneWidget);
    // Backing out leaves the list untouched.
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(find.byType(IssueCard), findsNWidgets(3));
  });

  testWidgets('edit opens a prefilled parameter form', (tester) async {
    await pumpHome(tester);

    await tester.tap(find.byIcon(Icons.more_vert).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit details'));
    await tester.pumpAndSettle();

    expect(find.text('Edit ticket'), findsOneWidget);
    // First card is the Samsung fridge fixture; its values seed the form.
    expect(find.widgetWithText(TextField, 'Samsung'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'RF28R7201'), findsOneWidget);
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

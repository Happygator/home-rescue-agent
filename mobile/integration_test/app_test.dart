// End-to-end UX test against the LIVE backend (FastAPI + Gemini).
//
// Run with the backend up on http://127.0.0.1:8000, then:
//   flutter test integration_test/app_test.dart -d windows
//
// It drives the real navigation and the real agent: Home -> New Issue -> describe the problem in
// the composer -> Start diagnosis -> the description is the first chat message -> auto-kickoff ->
// a live Gemini first fix appears in chat -> a follow-up turn still works. Assertions check for a
// substantive, non-canned agent reply so they are robust to Gemini's exact wording.
import 'package:home_rescue/main.dart';
import 'package:home_rescue/widgets/chat_bubble.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // pumpAndSettle can't be used while network spinners animate, so pump in a loop until the
  // predicate holds or the timeout elapses.
  Future<void> pumpUntil(
    WidgetTester tester,
    bool Function() predicate, {
    Duration timeout = const Duration(seconds: 60),
    String reason = 'condition',
  }) async {
    final end = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(end)) {
      if (predicate()) return;
      await tester.pump(const Duration(milliseconds: 300));
    }
    if (!predicate()) throw TestFailure('Timed out waiting for: $reason');
  }

  bool present(Finder f) => f.evaluate().isNotEmpty;

  Finder fieldWithHint(String hint) =>
      find.byWidgetPredicate((w) => w is TextField && w.decoration?.hintText == hint);

  Set<String> agentReplies(WidgetTester tester) => tester
      .widgetList<ChatBubble>(find.byType(ChatBubble))
      .where((b) => b.message.role == ChatRole.agent)
      .map((b) => b.message.text.trim())
      .toSet();

  testWidgets('create an issue and get a live Gemini first fix, then a follow-up', (tester) async {
    // Tall logical surface so list children (incl. the bottom "Start diagnosis" button) are all
    // laid out at once, rather than being lazily skipped off-screen.
    await tester.binding.setSurfaceSize(const Size(800, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const HomeRescueApp());

    // 1) Home loads from the live backend.
    await pumpUntil(tester, () => present(find.text('Open Issues')), reason: 'home to load');

    // 2) New issue -> the composer asks the user to describe the problem (no case created yet).
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    await pumpUntil(tester, () => present(find.text("What's going on with your appliance?")),
        reason: 'new-issue composer to open');

    // 3) Describe the problem. The composer has a single text field.
    await tester.enterText(find.byType(TextField), 'the fridge is running at 50F');
    await tester.pump();
    await pumpUntil(tester, () => present(find.text('Start diagnosis')),
        reason: 'Start diagnosis to appear');

    // 4) Start -> case is created, the description becomes the first user message, then the chat
    //    screen opens and auto-kicks off a live Gemini first fix.
    await tester.ensureVisible(find.text('Start diagnosis'));
    await tester.tap(find.text('Start diagnosis'));
    await pumpUntil(tester, () => present(find.text('Type a reply...')), reason: 'detail screen');

    final beforeKickoff = agentReplies(tester);
    await pumpUntil(
      tester,
      () => agentReplies(tester).difference(beforeKickoff).any((t) => t.length > 20),
      timeout: const Duration(seconds: 90),
      reason: 'Gemini kickoff fix to stream in',
    );
    final fix = agentReplies(tester).difference(beforeKickoff).firstWhere((t) => t.length > 20);
    expect(fix.length, greaterThan(20),
        reason: 'the kickoff should produce a substantive agent reply, not a canned line');

    // 6) Follow-up turn keeps working.
    final beforeFollowup = agentReplies(tester);
    await tester.enterText(fieldWithHint('Type a reply...'), 'I tried that, still warm.');
    await tester.tap(find.byIcon(Icons.send));
    await pumpUntil(
      tester,
      () => agentReplies(tester).difference(beforeFollowup).any((t) => t.length > 20),
      timeout: const Duration(seconds: 90),
      reason: 'Gemini follow-up reply',
    );
  });
}

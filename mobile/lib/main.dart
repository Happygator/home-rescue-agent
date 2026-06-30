import 'package:flutter/material.dart';
import 'config.dart';
import 'theme.dart';
import 'nav.dart';
import 'device_id.dart';
import 'screens/root_scaffold.dart';
import 'screens/issue_detail_screen.dart';
import 'screens/escalation_screen.dart';
import 'screens/new_issue_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Surface which backend this build talks to (helps catch a dev/prod mismatch at a glance).
  debugPrint('[HomeRescue] backend: ${AppConfig.baseUrl} (env: ${AppConfig.environment})');
  // Establish this device's anonymous user id before the first API call.
  await DeviceId.init();
  runApp(const HomeRescueApp());
}

// Optional deep-link entry point used for deterministic screenshots/QA. Normal launches
// (no dart-define) land on Home. Build with e.g.
//   flutter build web --dart-define=START_ROUTE=escalation --dart-define=START_CASE=case-9c4f7a02
const _startRoute = String.fromEnvironment('START_ROUTE');
const _startCase = String.fromEnvironment('START_CASE', defaultValue: 'case-7f3a9c21');

class HomeRescueApp extends StatelessWidget {
  const HomeRescueApp({super.key});

  Widget _home() {
    switch (_startRoute) {
      case 'detail':
        return IssueDetailScreen(caseId: _startCase);
      case 'escalation':
        return EscalationScreen(caseId: _startCase);
      case 'new':
        return const NewIssueScreen();
      default:
        return const RootScaffold();
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'HomeRescue',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        navigatorObservers: [routeObserver],
        home: _home(),
      );
}

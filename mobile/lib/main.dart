import 'package:flutter/material.dart';
import 'theme.dart';
import 'screens/home_screen.dart';
import 'screens/issue_detail_screen.dart';
import 'screens/escalation_screen.dart';
import 'screens/new_issue_screen.dart';

void main() => runApp(const ApplianceFixerApp());

// Optional deep-link entry point used for deterministic screenshots/QA. Normal launches
// (no dart-define) land on Home. Build with e.g.
//   flutter build web --dart-define=START_ROUTE=escalation --dart-define=START_CASE=case-9c4f7a02
const _startRoute = String.fromEnvironment('START_ROUTE');
const _startCase = String.fromEnvironment('START_CASE', defaultValue: 'case-7f3a9c21');

class ApplianceFixerApp extends StatelessWidget {
  const ApplianceFixerApp({super.key});

  Widget _home() {
    switch (_startRoute) {
      case 'detail':
        return IssueDetailScreen(caseId: _startCase);
      case 'escalation':
        return EscalationScreen(caseId: _startCase);
      case 'new':
        return const NewIssueScreen();
      default:
        return const HomeScreen();
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Appliance Fixer',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        home: _home(),
      );
}

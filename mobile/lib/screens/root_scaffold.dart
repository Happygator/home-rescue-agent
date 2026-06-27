import 'package:flutter/material.dart';
import '../theme.dart';
import 'home_screen.dart';
import 'launchpad_screen.dart';

/// Root shell. The app opens on the colorful Launchpad ("New") tab; the user's existing issues live
/// behind the "My issues" tab. An IndexedStack keeps both alive so switching tabs preserves the
/// list's loaded data and scroll position.
class RootScaffold extends StatefulWidget {
  const RootScaffold({super.key});

  @override
  State<RootScaffold> createState() => _RootScaffoldState();
}

class _RootScaffoldState extends State<RootScaffold> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: IndexedStack(
        index: _index,
        children: const [
          LaunchpadScreen(),
          HomeScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        backgroundColor: AppColors.card,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.textFaint,
        showUnselectedLabels: true,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.add_circle_outline),
            activeIcon: Icon(Icons.add_circle),
            label: 'New',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.format_list_bulleted),
            label: 'My issues',
          ),
        ],
      ),
    );
  }
}

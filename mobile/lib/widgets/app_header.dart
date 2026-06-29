import 'package:flutter/material.dart';
import '../theme.dart';

class AppHeader extends StatelessWidget {
  final String title;
  final bool showBack;
  final Widget? trailing;
  final bool homeBrand; // when true, show the wrench before the title
  const AppHeader({super.key, required this.title, this.showBack = false, this.trailing, this.homeBrand = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [AppColors.headerTop, AppColors.headerBottom]),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
          child: Row(
            children: [
              if (showBack)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: GestureDetector(
                    onTap: () => Navigator.of(context).maybePop(),
                    child: const Icon(Icons.arrow_back_ios_new, color: Colors.white, size: 18),
                  ),
                ),
              if (homeBrand)
                const Padding(
                  padding: EdgeInsets.only(right: 8),
                  child: Icon(Icons.build, color: Colors.white, size: 18),
                ),
              Expanded(
                child: Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 17)),
              ),
              if (trailing != null) trailing!,
            ],
          ),
        ),
      ),
    );
  }
}

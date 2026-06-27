import 'dart:ui';

import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import 'new_issue_screen.dart';

/// The colorful "What's broken?" landing surface (the "New" tab). Its whole job is to start a new
/// issue: a hero, a primary CTA, and per-appliance quick-start tiles. Previous issues live on the
/// other bottom-nav tab, not here.
class LaunchpadScreen extends StatelessWidget {
  const LaunchpadScreen({super.key});

  static const _heroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF3B82F6), Color(0xFF7C3AED)],
  );
  static const _ctaGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF2563EB), Color(0xFF4F46E5), Color(0xFF7C3AED)],
  );
  static const _accentGradient = LinearGradient(
    colors: [Color(0xFF2563EB), Color(0xFF7C3AED), Color(0xFFF59E0B)],
  );

  void _startNewIssue(BuildContext context, {String? appliance}) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => NewIssueScreen(appliance: appliance)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Column(
        children: [
          const AppHeader(
            title: 'HomeRescue',
            homeBrand: true,
            trailing: _GradientAvatar(),
          ),
          Container(
            height: 3,
            decoration: const BoxDecoration(gradient: _accentGradient),
          ),
          Expanded(
            child: Stack(
              children: [
                const _Aurora(),
                ListView(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 28),
                  children: [
                    const SizedBox(height: 8),
                    Center(
                      child: Container(
                        width: 92,
                        height: 92,
                        decoration: BoxDecoration(
                          gradient: _heroGradient,
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF0F172A).withOpacity(0.10),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.build,
                          color: Colors.white,
                          size: 38,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      "What's broken?",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textTitle,
                      ),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Describe the problem and the assistant will walk you through the fix, step by step.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: AppColors.textMuted,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 28),
                    GestureDetector(
                      onTap: () => _startNewIssue(context),
                      child: Container(
                        height: 58,
                        decoration: BoxDecoration(
                          gradient: _ctaGradient,
                          borderRadius: BorderRadius.circular(14),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF4F46E5).withOpacity(0.30),
                              blurRadius: 14,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 22,
                              height: 22,
                              decoration: BoxDecoration(
                                color: Colors.white.withOpacity(0.25),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.add,
                                color: Colors.white,
                                size: 16,
                              ),
                            ),
                            const SizedBox(width: 12),
                            const Text(
                              'Start a new issue',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Just describe it in your own words · one photo optional',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 12.5,
                        color: AppColors.textFaint,
                      ),
                    ),
                    const SizedBox(height: 28),
                    const Text(
                      'OR JUMP STRAIGHT IN',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textFaint,
                        letterSpacing: 0.4,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        _ApplianceTile(
                          label: 'Refrigerator',
                          icon: Icons.kitchen,
                          bg: const Color(0xFFEFF6FF),
                          border: const Color(0xFFDBEAFE),
                          fg: const Color(0xFF1D4ED8),
                          onTap: () => _startNewIssue(
                            context,
                            appliance: 'refrigerator',
                          ),
                        ),
                        const SizedBox(width: 9),
                        _ApplianceTile(
                          label: 'Dishwasher',
                          icon: Icons.water_drop,
                          bg: const Color(0xFFECFEFF),
                          border: const Color(0xFFCFFAFE),
                          fg: const Color(0xFF0E7490),
                          onTap: () =>
                              _startNewIssue(context, appliance: 'dishwasher'),
                        ),
                        const SizedBox(width: 9),
                        _ApplianceTile(
                          label: 'Washer',
                          icon: Icons.local_laundry_service,
                          bg: const Color(0xFFF5F3FF),
                          border: const Color(0xFFEDE9FE),
                          fg: const Color(0xFF6D28D9),
                          onTap: () =>
                              _startNewIssue(context, appliance: 'washer'),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Soft, blurred color blobs behind the hero (the "aurora" backdrop from the mockup).
class _Aurora extends StatelessWidget {
  const _Aurora();

  Widget _blob(double size, Color color) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
  );

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: 60, sigmaY: 60),
        child: Opacity(
          opacity: 0.5,
          child: Stack(
            children: [
              Positioned(
                right: -40,
                top: 20,
                child: _blob(210, const Color(0xFF93C5FD)),
              ),
              Positioned(
                left: -60,
                top: 120,
                child: _blob(230, const Color(0xFFC4B5FD)),
              ),
              Positioned(
                right: -10,
                top: 200,
                child: _blob(160, const Color(0xFFFCD34D)),
              ),
              Positioned(
                left: 60,
                top: -10,
                child: _blob(140, const Color(0xFFA7F3D0)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One tinted quick-start tile (icon + label) that opens the new-issue composer.
class _ApplianceTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color bg;
  final Color border;
  final Color fg;
  final VoidCallback onTap;
  const _ApplianceTile({
    required this.label,
    required this.icon,
    required this.bg,
    required this.border,
    required this.fg,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 80,
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: border),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: fg, size: 26),
              const SizedBox(height: 8),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: fg,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A gradient version of the account avatar, used in the Launchpad header.
class _GradientAvatar extends StatelessWidget {
  const _GradientAvatar();
  @override
  Widget build(BuildContext context) => Container(
    width: 30,
    height: 30,
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        colors: [Color(0xFF2563EB), Color(0xFF7C3AED), Color(0xFFF59E0B)],
      ),
      shape: BoxShape.circle,
    ),
    alignment: Alignment.center,
    child: const Text(
      'A',
      style: TextStyle(
        color: Colors.white,
        fontWeight: FontWeight.w700,
        fontSize: 12,
      ),
    ),
  );
}

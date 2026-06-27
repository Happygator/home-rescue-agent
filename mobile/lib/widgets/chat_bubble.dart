import 'package:flutter/material.dart';
import '../theme.dart';

enum ChatRole { agent, user, safety }

class ChatMessage {
  final ChatRole role;
  String text;
  // Optional fully-qualified URL of an image attached to this message.
  final String? imageUrl;
  // Short, pre-formatted clock label (e.g. "10:34 AM") shown beneath the bubble to
  // indicate when the message - typically a sent photo - was delivered.
  final String? sentAtLabel;
  ChatMessage(this.role, this.text, {this.imageUrl, this.sentAtLabel});
}

class ChatBubble extends StatelessWidget {
  final ChatMessage message;
  const ChatBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final maxW = MediaQuery.of(context).size.width * 0.78;
    if (message.role == ChatRole.safety) {
      return Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(color: AppColors.safetyBg, borderRadius: BorderRadius.circular(8)),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(String.fromCharCode(0x26A0), style: const TextStyle(color: AppColors.safetyText, fontSize: 13)),
            const SizedBox(width: 8),
            Expanded(child: Text(message.text, style: const TextStyle(color: AppColors.safetyText, fontSize: 11.5, height: 1.35))),
          ],
        ),
      );
    }
    final isUser = message.role == ChatRole.user;
    // An empty agent bubble means a reply is streaming in (kickoff or a turn). Show a typing
    // placeholder instead of a blank bubble so the wait for Gemini reads as "thinking", not broken.
    final isTyping = message.role == ChatRole.agent && message.text.trim().isEmpty;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            constraints: BoxConstraints(maxWidth: maxW),
            margin: const EdgeInsets.only(bottom: 2),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: isUser ? AppColors.userBubble : AppColors.card,
              borderRadius: BorderRadius.circular(14),
              border: isUser ? null : Border.all(color: AppColors.agentBubbleBorder),
            ),
            child: isTyping
                ? const _TypingDots()
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (message.imageUrl != null) ...[
                        _SentImage(url: message.imageUrl!),
                        if (message.text.trim().isNotEmpty) const SizedBox(height: 8),
                      ],
                      if (message.text.trim().isNotEmpty)
                        Text(message.text,
                            style: TextStyle(
                                fontSize: 12,
                                height: 1.35,
                                color: isUser ? AppColors.userBubbleText : AppColors.textBody2)),
                    ],
                  ),
          ),
          if (message.sentAtLabel != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10, left: 2, right: 2),
              child: Text(message.sentAtLabel!,
                  style: const TextStyle(fontSize: 10.5, color: AppColors.textFaint)),
            )
          else
            const SizedBox(height: 10),
        ],
      ),
    );
  }
}

/// A tappable inline thumbnail for an image attached to a chat message. Tapping opens a
/// full-screen, pinch-to-zoom viewer - the "view the image" affordance users expect.
class _SentImage extends StatelessWidget {
  final String url;
  const _SentImage({required this.url});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        PageRouteBuilder(
          opaque: false,
          barrierColor: Colors.black87,
          pageBuilder: (_, _, _) => _ImageViewer(url: url),
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Stack(
          alignment: Alignment.bottomRight,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 240),
              child: Image.network(
                url,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => const Padding(
                  padding: EdgeInsets.symmetric(vertical: 6),
                  child: Text('Photo unavailable',
                      style: TextStyle(fontSize: 11, color: AppColors.textFaint)),
                ),
              ),
            ),
            Container(
              margin: const EdgeInsets.all(6),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: const [
                  Icon(Icons.zoom_in, size: 13, color: Colors.white),
                  SizedBox(width: 3),
                  Text('View',
                      style: TextStyle(fontSize: 10.5, color: Colors.white, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Full-screen image viewer: pinch/drag to zoom, tap the backdrop or the close button to dismiss.
class _ImageViewer extends StatelessWidget {
  final String url;
  const _ImageViewer({required this.url});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: InteractiveViewer(
              minScale: 1,
              maxScale: 5,
              child: Center(
                child: Image.network(
                  url,
                  fit: BoxFit.contain,
                  errorBuilder: (_, _, _) => const Text('Photo unavailable',
                      style: TextStyle(fontSize: 13, color: Colors.white70)),
                ),
              ),
            ),
          ),
          SafeArea(
            child: Align(
              alignment: Alignment.topRight,
              child: IconButton(
                icon: const Icon(Icons.close, color: Colors.white, size: 28),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A static three-dot "thinking" placeholder shown in an agent bubble while a reply streams in.
/// Kept static (no repeating animation) so widget tests using pumpAndSettle still settle.
class _TypingDots extends StatelessWidget {
  const _TypingDots();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final opacity in const [0.9, 0.6, 0.35])
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2),
            child: Opacity(
              opacity: opacity,
              child: Container(
                width: 6,
                height: 6,
                decoration: const BoxDecoration(color: AppColors.textFaint, shape: BoxShape.circle),
              ),
            ),
          ),
      ],
    );
  }
}

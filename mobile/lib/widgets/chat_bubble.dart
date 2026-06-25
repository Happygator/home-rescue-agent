import 'package:flutter/material.dart';
import '../theme.dart';

enum ChatRole { agent, user, safety }

class ChatMessage {
  final ChatRole role;
  String text;
  ChatMessage(this.role, this.text);
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
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: maxW),
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser ? AppColors.userBubble : AppColors.card,
          borderRadius: BorderRadius.circular(14),
          border: isUser ? null : Border.all(color: AppColors.agentBubbleBorder),
        ),
        child: Text(message.text,
            style: TextStyle(fontSize: 12, height: 1.35, color: isUser ? AppColors.userBubbleText : AppColors.textBody2)),
      ),
    );
  }
}

# Using Sentio

Start with `python scripts/dev/dev_start.py --port 8001` from the project directory.
Open http://127.0.0.1:8001 and leave the terminal open. Stop with Ctrl+C.

1. Create an account or sign in. Save the recovery key displayed after registration.
2. On Today, choose **Add your first notes**. Upload a readable TXT, PDF or DOCX
   in Library. Wait for **Ready to study**. Upload progress reports actual stages;
   keyword retrieval can remain available when semantic retrieval is unavailable.
3. Choose **Study** beside those notes, check the subject and topic, and start.
   Optionally pick a **Goal for this session** from the goals you added on Today.
   The tutor sees that goal as background. Changing or completing it stops any
   answer or practice still being prepared for the old goal.
4. Ask a question about the selected notes. Sources show the passages used.
   Stop cancels generation. If generation fails validation, Sentio may show quoted
   passages explicitly labelled as a fallback, rather than claim a verified explanation.
   Selected-note chat always checks those sources, including requests to review or
   summarize them. Use Today for your revision plan and saved-practice progress.
5. Choose **Try a quiz** or **Make flashcards**. These use the current study notes
   without asking you to configure another session. Start with three items.
   Source-recall quizzes are labelled and test recalled wording, not deep understanding.
   Every saved quiz and card shows how it was made: which model generated it, or that
   it was quoted from your notes, and which pages it used. If a question or answer is
   wrong, choose **Edit this question**. Earlier results keep their grades; answers
   you submit afterwards use your correction, and the quiz is marked as edited.
6. Review cards with Again, Hard, Good or Easy. Due reviews and saved work survive
   restart. Progress estimates include self-reported ratings; they are not exam results.

To change notes, return to Library and choose Study on the new document. Saved
practice remains accessible. Settings contains diagnostics, data export and account
controls. The camera-based emotion feature is optional and off unless your
installation enables it (see EMOTION.md).

## Forgotten password

Existing accounts: while signed in, open Settings and create a recovery key using
 your current password. Download it and store it somewhere private.

On the sign-in screen choose **Forgot password?**, enter your email, saved recovery
key and new password. Successful recovery invalidates previous sign-ins and consumes
that key. Save the replacement key immediately. Keys are displayed once and stored
only as hashes on the server. There is no email delivery service in this local app.
If both your password and recovery key are lost, the web interface cannot verify
ownership safely; do not delete the database or expect an email-only reset.

# Using Sentio

Start with `python scripts/dev/dev_start.py --port 8001` from the project directory.
Open http://127.0.0.1:8001 and leave the terminal open. Stop with Ctrl+C.

1. Create an account or sign in. Save the recovery key displayed after registration.
2. On Today, choose **Add your first notes**. In Library, optionally pick or create a
   **Course** (for example "Operating Systems"), then upload one or several files:
   PowerPoint (PPTX), PDF, DOCX or TXT. Each slide of a deck becomes its own page, so
   citations say "slide 4". Old `.ppt` files must be saved as `.pptx` first. Wait for
   **Ready to study**. You can move a lecture to another course at any time; deleting a
   course keeps its lectures. Upload progress reports actual stages;
   keyword retrieval can remain available when semantic retrieval is unavailable.
3. Choose **Study** beside a lecture, or **Study course** to ask about every lecture in
   a course (lectures added later are included automatically). Studying starts at once;
   the topic comes from the notes' opening line. Choose **Summarize these notes** for a short summary, key
   concepts and suggested questions; click a question to ask it. The overview is saved,
   so it appears instantly next time.
   Optionally pick a **Goal for this session** from the goals you added on Today.
   The tutor sees that goal as background. Changing or completing it stops any
   answer or practice still being prepared for the old goal.
4. Ask a question about the selected notes. The passages found appear first, while the
   answer is written. Click any citation, inline or below the answer, to read the
   exact passage. Stop cancels generation. If generation fails validation, Sentio may show quoted
   passages explicitly labelled as a fallback, rather than claim a verified explanation.
   Selected-note chat always checks those sources, including requests to review or
   summarize them. Use Today for your revision plan and saved-practice progress.
   The difficulty you chose stays unless you ask ("make it harder", "explain it more
   simply") or your quiz answers show it: 3 correct in a row steps up, 2 wrong steps
   down. Each change appears with its reason and an **Undo**, which keeps your level
   until you ask for a change.
5. Choose **Try a quiz** or **Make flashcards**. These use the current study notes
   without asking you to configure another session. Start with three items.
   Choose **Check answer** for instant feedback on one question; nothing is recorded
   until you submit the quiz.
   Source-recall quizzes are labelled and test recalled wording, not deep understanding.
   Every saved quiz and card shows how it was made: which model generated it, or that
   it was quoted from your notes, and which pages it used. If a question or answer is
   wrong, choose **Edit this question**. Earlier results keep their grades; answers
   you submit afterwards use your correction, and the quiz is marked as edited.
6. Review cards with Again, Hard, Good or Easy. Each button shows when the card will
   come back; the FSRS scheduler sets the interval so you review a card when your chance
   of recalling it has fallen to about 90%. Due reviews and saved work survive restart.
   Progress estimates include self-reported ratings; they are not exam results.
7. See how each lecture is going: open **Progress by topic** under a course, or
   **Topics** beside a lecture. Topics follow slide titles (PDF page headings; Word and
   text files form one topic). Each topic is **Not started**, **Practising** or
   **Ready** (at least 5 answers, and 4 of the last 5 correct). **Weak topics** lists
   practised topics below that bar with their slides; **Review** opens the tutor on the
   topic and **Practise** prepares a quiz on it. **Practise weak topics** covers all of
   them at once. You can rename a topic or merge it into the one above. Only quizzes
   taken after this update count, and the result is a practice estimate.
8. Add the course **Syllabus** in the same panel: paste it, or choose its PDF, Word,
   PowerPoint or text file. Sentio splits it into units and topics (skipping textbooks,
   references and outcomes) and matches each topic to your lecture topics. The course
   then shows "62% of the syllabus ready", and topics with no matching notes are marked
   **Not in your notes yet**, so you know what to collect before the exam. If a match is
   wrong, pick the right lecture topic or "Not in my notes" from its list.

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

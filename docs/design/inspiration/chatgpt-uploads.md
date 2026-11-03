# ChatGPT: adding files and waiting for answers

- **Checked:** 2026-11-03.
- **Sources:** chatgpt.com, signed out, so no files were uploaded; and OpenAI's [Uploading files and audio to ChatGPT](https://help.openai.com/en/articles/8555545-uploading-files-and-audio-to-chatgpt), updated 2026-11-01.
- **How sure each point is:**
  - **Seen:** observed in this session.
  - **Documented:** from OpenAI's help article.
  - **Familiar:** widely known ChatGPT behaviour, not re-checked here because uploading needs an account.

## How ChatGPT handles files

1. **Files go in where you're already working.** A `+` button sits inside the message box and opens Camera, Photos and Files. (Seen.) There is no separate upload page: you attach the file to the question you're about to ask. (Documented)
2. **Several at once.** The file pickers accept multiple files. (Seen)
3. **Drop anywhere.** Dragging a file over the window shows a full-window drop target, not a small box. (Familiar)
4. **Each file becomes a chip.** It shows the name, the file type and a small progress ring while uploading, plus a remove ✕. Send waits until the upload finishes. (Familiar)
5. **Waiting is shown inside the conversation.** While answering, a short status line such as "Reading documents" shows, with a soft shimmer. (Familiar)
6. **Limits are clear.** It lists the formats (DOCX, PDF, TXT, PPTX, spreadsheets, images, audio) and the size limits (512 MB per document, 2 million tokens, 20 MB per image). Failures are explained: "upload limit reached" errors come with a retry time. (Documented)
7. **What it can't show.** It does not show how much of the rolling upload quota is used or left. (Documented)
8. **PDF images.** Charts and diagrams in PDFs are read when the PDF is attached directly; project and GPT knowledge files may skip images. (Documented)
9. **Deleting is spelled out.** Deleting a chat does not delete a saved file, and each is removed separately. (Documented)

## How Sentio handles them today

From `src/sentio/static/js/views/documents.js` and `src/sentio/static/js/core/jobs.js`.

- **Uploads happen only in the Library,** in a "1. Add your notes" card with a dashed drop box. To study a file, you go back to Study and pick it from "Notes to use".
- **Several files upload one after another,** with a single text line ("Uploading 2 of 5: …"), then a summary of what was added and what wasn't.
- **Progress uses honest stage labels,** such as "Reading the text in your document…" and "Making your notes searchable. The first upload can take longer…". Jobs survive a refresh and can be cancelled.
- **Status in the library** uses emoji: ✅ Ready to study, ⏳ Processing, ❌ Needs retry. The drop box uses 📄.
- **A failed upload asks you to choose the file again** before you can retry.
- **Limits are stated up front:** formats, 20 MiB per file, and whether OCR is available.
- **Answers already show sources first.** The retrieved passages stream in before the answer text. ChatGPT does not do this.

## What Sentio can learn

Sentio already does better on honesty: named stages, sources before the answer, and stated limits. The lessons are about where uploads happen and how they feel.

| Lesson from ChatGPT         | Change for Sentio                                                                                                                       | Fits Sentio because                                                  |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Attach where you're working | Accept files dropped onto Study (and a `+` beside "Notes to use"). Upload them, then select them for the current session automatically. | The main flow is upload → ask. Today it takes a trip to the Library. |
| One chip per file           | Show each file in the batch as its own row: name, type, its current stage, and remove or cancel.                                        | One shared text line hides which file is slow or failed.             |
| Drop anywhere               | A calm full-view drop target on Library and Study.                                                                                      | Bigger target, same honesty.                                         |
| Status inside the flow      | Keep the stage labels, shown as a quiet line where the result will appear. Use a subtle pulse rather than a spinner.                    | It matches the Apple-style "one shared speed" motion note.           |
| Retry without re-choosing   | Keep the chosen file in memory for the session, so retry is one click.                                                                  | Today a failure forces you to find the file again.                   |
| Real icons                  | Replace ✅ ⏳ ❌ 📄 with the existing topic-state pill style (Ready, Processing, Needs retry) and a drawn file icon.                    | Emoji used as icons is one of the "AI slop" signals.                 |

## What not to copy

- **Upload quotas and sign-up:** Sentio is local, with no rate limits and no account with a vendor.
- **Reading images inside PDFs:** Sentio's OCR is optional and limited to 20 scanned pages. Don't imply it reads charts.
- **Fully hidden progress:** Sentio's named stages are better. Keep them.

# Web walkthrough

Start the backend and frontend using the [README](../README.md). Open the web
client and verify that it shows the online GitHub source and a connected backend.
Only the backend reads the configured model and optional GitHub credentials.

## A question and follow-up

1. Ask: `GitHub 账号被暂停后，申诉期限是多久？请用中文回答。`
2. Wait for the answer and select a numbered citation. The source panel shows
   the original excerpt, file path, line range and immutable commit link.
3. Ask: `那应该在哪里提交？`
4. Verify that the follow-up is interpreted using the preceding completed turn.
   The agent must still read its policy evidence again for the new question.
5. Use **Open original on GitHub** to compare the excerpt with the cited version.

These captures show real responses from the online-reading interface. They are
examples of the interaction, not a guarantee that every model response is correct.

![Online question and follow-up](screenshots/online-policy-answer.png)

![Exact source excerpt and versioned link](screenshots/online-policy-chat.png)

## Temporary history

Choose **New conversation** to clear turns and the source panel. A new browser tab
starts empty; refresh also clears the current page. No history can be restored.
Failed questions remain editable and do not enter subsequent history.

When a new response contains no citations, its source panel is cleared rather
than displaying evidence from a previous response. See [UI behavior](UI.md) for
the complete interaction contract and [verification](VERIFICATION.md) for checks.

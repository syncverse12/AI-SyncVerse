from realtime_update import RAGUpdater

updater = RAGUpdater("data/processed")

# simulate new issue
updater.add_document(
    title="Browser session crash when reopening tabs",
    content="The browser crashes when restoring session tabs after restart."
)

# save changes
updater.save()

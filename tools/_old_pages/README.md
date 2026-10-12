# Old pages, pending trash

Replaced by Voice Studio (`tools/studio`, port 8930). Kept here until the new app has been tested, then to be trashed.

- `pasqal_lab/`: the Pasqal clone workbench (was :8910). Nothing else imports it.
- `voice_audit/audit.html`: the voice audit page (was :8907). Its server, `tools/voice_design/audit_server.py`, stays where
  it is because the studio imports its ranking and keep helpers; that server's `/` page will now fail without this file.

Still in use and not moved: FX Lab (:8908), match review (:8920), render QA (:8951).

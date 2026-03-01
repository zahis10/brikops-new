"""
Backend tests for Evidence Upload functionality (iOS Evidence-First Flow)
=========================================================================
QUARANTINE WAIVER — 2026-02-17
Reason: These tests belong to a legacy BedekPro inspection module that has been
        superseded by the Contractor Ops task management system. The endpoints
        tested (/api/media/upload-evidence, /api/inspections/{id}/pending-evidence,
        /api/evidence-findings) do NOT exist in the Contractor Ops backend.
        Running these tests produces 9 connection/import errors because the
        BedekPro API surface was never ported to this codebase.

Ticket: CONTRACTOR-OPS-QUARANTINE-001
Owner: Backend team
Target restore date: 2026-04-01 (Q2 sprint — evaluate whether BedekPro
        evidence flow should be reimplemented or formally removed)

Decision: QUARANTINE — all tests marked with pytest.skip() pending evaluation.
Approved by: Project Owner (sprint review 2026-02-17)
"""

import pytest

QUARANTINE_REASON = (
    "QUARANTINE: BedekPro evidence endpoints not present in Contractor Ops. "
    "Ticket: CONTRACTOR-OPS-QUARANTINE-001. "
    "Target restore: 2026-04-01."
)


@pytest.mark.skip(reason=QUARANTINE_REASON)
class TestEvidenceUpload:
    """Tests for POST /api/media/upload-evidence endpoint — QUARANTINED"""

    def test_upload_evidence_success(self):
        pass

    def test_upload_evidence_invalid_inspection_id(self):
        pass

    def test_upload_evidence_no_file(self):
        pass

    def test_upload_evidence_unauthorized(self):
        pass


@pytest.mark.skip(reason=QUARANTINE_REASON)
class TestPendingEvidence:
    """Tests for GET /api/inspections/{id}/pending-evidence endpoint — QUARANTINED"""

    def test_get_pending_evidence_success(self):
        pass

    def test_get_pending_evidence_invalid_inspection(self):
        pass


@pytest.mark.skip(reason=QUARANTINE_REASON)
class TestEvidenceFindings:
    """Tests for POST /api/evidence-findings endpoint — QUARANTINED"""

    def test_create_evidence_finding_success(self):
        pass

    def test_create_evidence_finding_invalid_inspection(self):
        pass


@pytest.mark.skip(reason=QUARANTINE_REASON)
class TestEvidenceFindingsList:
    """Tests for GET /api/inspections/{id}/evidence-findings endpoint — QUARANTINED"""

    def test_get_evidence_findings_list(self):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

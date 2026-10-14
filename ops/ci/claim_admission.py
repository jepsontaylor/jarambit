#!/usr/bin/env python3
"""Launch the claim checker with an independently approved operator context.

Approval bytes/hash/registration enter through the trusted application's API,
never a command-line, environment or document-selected authority. The standalone
CLI remains a typed refusal until that application supplies a real context.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.reporting import claims
from assurance.testing.contracts import ContractError
from ops.ci import check_claims, rs_verdicts


def context_from_operator_approval(raw, *, approved_sha256, approved_registration,
                                   request_path, authority_path):
    """Expected approvals belong to the operator, independently of submitted inputs."""
    caller = claims.TrustedCaller.from_approved_bytes(raw, approved_sha256, approved_registration)
    caller.verify_current()
    return rs_verdicts.ReportingContext(caller, request_path, authority_path)


def main(argv=None, *, context=None):
    try:
        claims.require(context is not None, 'independent_caller_admission_unavailable')
        claims.require(type(context) is rs_verdicts.ReportingContext,
                       'independent_caller_admission_required')
        # A previous result must not survive an altered caller/source/binary.
        context.last_resolution = None
        context.last_report = None
        context.caller.verify_current()
    except (claims.Refusal, ContractError, OSError, UnicodeError, TypeError, KeyError, ValueError) as error:
        print('ERROR:', error)
        print('check_claims: 1 violation(s)')
        return 2
    return check_claims.main(argv, context=context)


if __name__ == '__main__':
    raise SystemExit(main())

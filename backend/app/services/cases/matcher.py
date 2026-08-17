from app.schemas.agent_outputs import Finding
from app.schemas.analysis_result import ClassicCaseMatch


class ClassicCaseMatcher:
    def match(
        self,
        cases: list[dict],
        intersection_type: str,
        findings: list[Finding],
        limit: int,
    ) -> list[ClassicCaseMatch]:
        issue_tags = {finding.category for finding in findings}
        ranked: list[tuple[float, dict, set[str]]] = []
        for case in cases:
            type_match = intersection_type in case.get("intersectionTypes", [])
            matched_tags = issue_tags.intersection(case.get("problemTags", []))
            score = min(1.0, (0.45 if type_match else 0.0) + 0.18 * len(matched_tags))
            if score > 0:
                ranked.append((score, case, matched_tags))
        ranked.sort(key=lambda item: item[0], reverse=True)

        results: list[ClassicCaseMatch] = []
        for score, case, matched_tags in ranked[:limit]:
            reason = "路口型態相近"
            if matched_tags:
                reason += f"，且同樣涉及 {', '.join(sorted(matched_tags))} 問題"
            results.append(
                ClassicCaseMatch(
                    id=case["id"],
                    title=case["title"],
                    location=case["location"],
                    summary=case["summary"],
                    sourceUrl=case["sourceUrl"],
                    beforeImageUrl=case.get("beforeImageUrl"),
                    afterImageUrl=case.get("afterImageUrl"),
                    matchReason=reason,
                    score=score,
                )
            )
        return results


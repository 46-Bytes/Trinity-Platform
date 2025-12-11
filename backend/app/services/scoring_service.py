"""
Scoring service for calculating module scores and RAG status
"""
from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP


class ScoringService:
    """Service for scoring diagnostic responses"""
    
    # Module mapping
    MODULES = {
        "M1": "Financial Clarity & Reporting",
        "M2": "Legal, Compliance & Property",
        "M3": "Owner Dependency & Operations",
        "M4": "People",
        "M5": "Customer, Product & Revenue Quality",
        "M6": "Brand, IP & Intangibles",
        "M7": "Tax, Compliance & Regulatory",
        "M8": "Due Diligence Preparation"
    }
    
    # RAG thresholds
    RAG_RED_THRESHOLD = 2.0
    RAG_AMBER_THRESHOLD = 4.0
    
    @staticmethod
    def calculate_module_scores(
        scored_rows: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate average scores for each module.
        
        Args:
            scored_rows: List of scored question responses with module assignments
            
        Returns:
            Dictionary mapping module codes to score data
            
        Example scored_row:
            {
                "question": "How has your financial performance been?",
                "response": "Better",
                "score": 5,
                "module": "M1"
            }
        """
        module_data = {}
        
        # Group scores by module
        for row in scored_rows:
            module = row.get("module")
            score = row.get("score")
            
            if not module or score is None:
                continue
            
            if module not in module_data:
                module_data[module] = {
                    "scores": [],
                    "questions": []
                }
            
            module_data[module]["scores"].append(score)
            module_data[module]["questions"].append({
                "question": row.get("question"),
                "response": row.get("response"),
                "score": score
            })
        
        # Calculate averages
        module_scores = {}
        for module, data in module_data.items():
            scores = data["scores"]
            total = sum(scores)
            count = len(scores)
            average = Decimal(total / count).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            
            module_scores[module] = {
                "module": module,
                "module_name": ScoringService.MODULES.get(module, module),
                "score": float(average),
                "count": count,
                "total": total,
                "questions": data["questions"]
            }
        
        return module_scores
    
    @staticmethod
    def determine_rag_status(score: float) -> str:
        """
        Determine RAG (Red/Amber/Green) status based on score.
        
        Args:
            score: Module average score (0-5)
            
        Returns:
            RAG status: "Red", "Amber", or "Green"
        """
        if score < ScoringService.RAG_RED_THRESHOLD:
            return "Red"
        elif score < ScoringService.RAG_AMBER_THRESHOLD:
            return "Amber"
        else:
            return "Green"
    
    @staticmethod
    def rank_modules(
        module_scores: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank modules by priority (lowest score = highest priority).
        
        Args:
            module_scores: Dictionary of module scores
            
        Returns:
            List of modules with rankings (sorted by priority)
        """
        # Convert to list and sort
        modules_list = list(module_scores.values())
        
        # Sort by score (ascending) and then by module name (alphabetically)
        modules_list.sort(key=lambda x: (x["score"], x["module"]))
        
        # Assign ranks
        for rank, module in enumerate(modules_list, start=1):
            module["rank"] = rank
            module["rag"] = ScoringService.determine_rag_status(module["score"])
        
        return modules_list
    
    @staticmethod
    def calculate_overall_score(
        module_scores: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Calculate overall diagnostic score (average of all module scores).
        
        Args:
            module_scores: Dictionary of module scores
            
        Returns:
            Overall score (0-5, 1 decimal place)
        """
        if not module_scores:
            return 0.0
        
        scores = [module["score"] for module in module_scores.values()]
        total = sum(scores)
        count = len(scores)
        average = Decimal(total / count).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        
        return float(average)
    
    @staticmethod
    def map_response_to_score(
        question_key: str,
        response_value: Any,
        scoring_map: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Map a single response to a score using the scoring map.
        
        Args:
            question_key: Key of the question (e.g., "financial_performance_since_acquisition")
            response_value: User's response value (e.g., "Better")
            scoring_map: The scoring map dictionary
            
        Returns:
            Tuple of (score, module) or (None, None) if not scoreable
        """
        if question_key not in scoring_map:
            return None, None
        
        question_map = scoring_map[question_key]
        module = question_map.get("module")
        values = question_map.get("values", {})
        
        # Convert response to string for matching
        response_str = str(response_value)
        
        if response_str not in values:
            return None, None
        
        score = values[response_str]
        
        return score, module
    
    @staticmethod
    def build_scored_rows(
        user_responses: Dict[str, Any],
        scoring_map: Dict[str, Any],
        diagnostic_questions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build scored rows from user responses.
        This manually creates what GPT would create, useful for validation.
        
        Args:
            user_responses: User's diagnostic responses
            scoring_map: Scoring map
            diagnostic_questions: Diagnostic survey structure
            
        Returns:
            List of scored rows
        """
        scored_rows = []
        
        # Build a map of question keys to question text
        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])
        
        # Process each response
        for question_key, response_value in user_responses.items():
            score, module = ScoringService.map_response_to_score(
                question_key, response_value, scoring_map
            )
            
            if score is not None and module is not None:
                scored_rows.append({
                    "question": question_text_map.get(question_key, question_key),
                    "question_key": question_key,
                    "response": response_value,
                    "score": score,
                    "module": module
                })
        
        return scored_rows
    
    @staticmethod
    def validate_scoring_data(
        ai_scoring_data: Dict[str, Any],
        user_responses: Dict[str, Any],
        scoring_map: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate AI-generated scoring data for accuracy.
        
        Args:
            ai_scoring_data: Scoring data from GPT
            user_responses: Original user responses
            scoring_map: Scoring map
            
        Returns:
            Validation results with warnings/errors
        """
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        scored_rows = ai_scoring_data.get("scored_rows", [])
        roadmap = ai_scoring_data.get("roadmap", [])
        
        # Check if scored_rows exists
        if not scored_rows:
            validation["errors"].append("No scored_rows found in AI response")
            validation["is_valid"] = False
            return validation
        
        # Calculate module scores from scored_rows
        module_scores = ScoringService.calculate_module_scores(scored_rows)
        
        # Validate roadmap scores match calculated scores
        if roadmap:
            for roadmap_item in roadmap:
                module = roadmap_item.get("module")
                roadmap_score = roadmap_item.get("score")
                
                if module in module_scores:
                    calculated_score = module_scores[module]["score"]
                    
                    # Allow small floating point differences
                    if abs(roadmap_score - calculated_score) > 0.1:
                        validation["warnings"].append(
                            f"Module {module}: Roadmap score ({roadmap_score}) "
                            f"differs from calculated score ({calculated_score})"
                        )
        
        # Check for missing scoreable questions
        expected_question_count = sum(
            1 for key in user_responses.keys()
            if key in scoring_map
        )
        actual_question_count = len(scored_rows)
        
        if expected_question_count != actual_question_count:
            validation["warnings"].append(
                f"Expected {expected_question_count} scored questions, "
                f"but got {actual_question_count}"
            )
        
        return validation


# Singleton instance
scoring_service = ScoringService()


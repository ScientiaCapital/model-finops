"""
Interactive CLI tool for testing AI Cost Optimizer with quality rating.

Features:
- Test prompts interactively with real-time results
- Rate responses for quality feedback
- View statistics and learning insights
- Browse request history

Usage:
    python -m app.cli_tester test     # Interactive testing mode
    python -m app.cli_tester stats    # View statistics
    python -m app.cli_tester history  # View request history
    python -m app.cli_tester insights # View learning insights
"""

import argparse
import asyncio
import sys

from app.complexity import get_complexity_metadata, score_complexity

# Add parent directory to path for imports
from app.database import CostTracker
from app.providers import init_providers
from app.router import Router


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print colored header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}\n")


def print_section(text: str) -> None:
    """Print section divider."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-' * len(text)}{Colors.END}")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


class CLITester:
    """Interactive CLI testing tool."""

    def __init__(self) -> None:
        """Initialize CLI tester with database and router."""
        self.cost_tracker = CostTracker()
        self.providers = init_providers()
        self.router = Router(self.providers)

        if not self.providers:
            print_error("No providers initialized! Check your API keys in .env")
            sys.exit(1)

        print_success(
            f"Initialized with {len(self.providers)} providers: {', '.join(self.providers.keys())}"
        )

    async def test_interactive(self) -> None:
        """Interactive testing mode with quality rating."""
        print_header("Interactive Testing Mode")
        print_info("Type 'quit' or 'exit' to stop\n")

        while True:
            try:
                # Get prompt from user
                prompt = input(f"\n{Colors.BOLD}Enter your prompt: {Colors.END}").strip()

                if prompt.lower() in ["quit", "exit", "q"]:
                    print_success("Exiting interactive mode")
                    break

                if not prompt:
                    print_warning("Empty prompt, please try again")
                    continue

                # Get max tokens (optional)
                max_tokens_input = input(
                    f"{Colors.BOLD}Max tokens (default: 200): {Colors.END}"
                ).strip()
                max_tokens = int(max_tokens_input) if max_tokens_input else 200

                # Analyze complexity
                await self._analyze_and_route(prompt, max_tokens)

            except KeyboardInterrupt:
                print_success("\n\nExiting interactive mode")
                break
            except Exception as e:
                print_error(f"Error: {str(e)}")

    async def _analyze_and_route(self, prompt: str, max_tokens: int) -> None:
        """Analyze prompt, route to provider, and handle rating."""
        print_section("Complexity Analysis")

        # Get complexity
        complexity = score_complexity(prompt)
        metadata = get_complexity_metadata(prompt)

        print(f"Classification: {Colors.BOLD}{complexity.upper()}{Colors.END}")
        print(f"Token count: {metadata['token_count']}")
        print(
            "Keywords found: "
            f"{', '.join(metadata['keywords_found']) if metadata['keywords_found'] else 'None'}"
        )

        # Check cache
        print_section("Cache Check")
        cached = self.cost_tracker.check_cache(prompt, max_tokens)

        if cached:
            print_success(f"Cache HIT! (hit count: {cached['hit_count']})")
            print(f"Provider: {cached['provider']}/{cached['model']}")
            print(f"Cost: ${cached['cost']:.6f} (saved by cache)")
            print(f"\n{Colors.BOLD}Response:{Colors.END}\n{cached['response'][:500]}...")

            # Record cache hit
            self.cost_tracker.record_cache_hit(cached["cache_key"])
            cache_key = cached["cache_key"]
            print_info("Recorded cache hit")

        else:
            print_info("Cache MISS - routing to LLM provider")

            # Get routing recommendation
            print_section("Routing Decision")
            provider_name, model_name, provider = self.router.select_provider(complexity, prompt)

            print(f"Selected: {Colors.BOLD}{provider_name}/{model_name}{Colors.END}")
            reasoning = self.router._get_routing_reasoning(complexity)
            print(f"Reasoning: {reasoning}")

            # Execute request
            print_section("Executing Request")
            print_info("Sending request to provider...")

            try:
                result = await self.router.execute(prompt, max_tokens)

                print_success("Request completed!")
                print(f"Provider: {result['provider']}/{result['model']}")
                print(f"Tokens: {result['tokens_in']} in, {result['tokens_out']} out")
                print(f"Cost: ${result['cost']:.6f}")
                print(f"Complexity: {result['complexity']}")

                print(f"\n{Colors.BOLD}Response:{Colors.END}\n{result['response'][:500]}...")

                # Store in cache
                self.cost_tracker.store_in_cache(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    response=result["response"],
                    provider=result["provider"],
                    model=result["model"],
                    complexity=result["complexity"],
                    tokens_in=result["tokens_in"],
                    tokens_out=result["tokens_out"],
                    cost=result["cost"],
                )

                # Log to database
                self.cost_tracker.log_request(
                    prompt=prompt,
                    complexity=result["complexity"],
                    provider=result["provider"],
                    model=result["model"],
                    tokens_in=result["tokens_in"],
                    tokens_out=result["tokens_out"],
                    cost=result["cost"],
                )

                cache_key = self.cost_tracker._generate_cache_key(prompt, max_tokens)

            except Exception as e:
                print_error(f"Request failed: {str(e)}")
                return

        # Quality rating
        await self._rate_response(cache_key)

    async def _rate_response(self, cache_key: str) -> None:
        """Prompt user to rate the response quality."""
        print_section("Quality Rating")
        print("Rate this response:")
        print(f"  {Colors.GREEN}1{Colors.END} = Upvote (good response)")
        print(f"  {Colors.RED}-1{Colors.END} = Downvote (poor response)")
        print(f"  {Colors.YELLOW}0{Colors.END} or Enter = Skip rating")

        rating_input = input(f"\n{Colors.BOLD}Your rating: {Colors.END}").strip()

        if not rating_input or rating_input == "0":
            print_info("Rating skipped")
            return

        try:
            rating = int(rating_input)
            if rating not in [1, -1]:
                print_warning("Invalid rating. Use 1 (upvote) or -1 (downvote)")
                return

            # Optional comment
            comment = input(f"{Colors.BOLD}Comment (optional): {Colors.END}").strip()

            # Add feedback
            self.cost_tracker.add_feedback(
                cache_key=cache_key, rating=rating, comment=comment if comment else None
            )

            # Update quality score
            quality_score = self.cost_tracker.update_quality_score(cache_key)

            emoji = "👍" if rating == 1 else "👎"
            print_success(
                f"{emoji} Rating recorded! Quality score: {quality_score:.2f}"
                if quality_score
                else f"{emoji} Rating recorded!"
            )

        except ValueError:
            print_warning("Invalid input. Rating skipped.")

    def show_stats(self) -> None:
        """Display usage statistics."""
        print_header("Usage Statistics")

        stats = self.cost_tracker.get_usage_stats()

        # Overall stats
        print_section("Overall")
        print(f"Total requests: {stats['overall']['total_requests']}")
        print(f"Total cost: ${stats['overall']['total_cost']:.6f}")
        print(f"Average cost/request: ${stats['overall']['avg_cost_per_request']:.6f}")
        print(f"Total tokens in: {stats['overall']['total_tokens_in']:,}")
        print(f"Total tokens out: {stats['overall']['total_tokens_out']:,}")

        # Provider breakdown
        if stats["by_provider"]:
            print_section("By Provider")
            for provider in stats["by_provider"]:
                print(f"\n{Colors.BOLD}{provider['provider']}{Colors.END}:")
                print(f"  Requests: {provider['request_count']}")
                print(f"  Total cost: ${provider['total_cost']:.6f}")
                print(f"  Avg cost: ${provider['avg_cost']:.6f}")

        # Complexity breakdown
        if stats["by_complexity"]:
            print_section("By Complexity")
            for complexity in stats["by_complexity"]:
                print(f"\n{Colors.BOLD}{complexity['complexity']}{Colors.END}:")
                print(f"  Requests: {complexity['request_count']}")
                print(f"  Total cost: ${complexity['total_cost']:.6f}")
                print(f"  Avg cost: ${complexity['avg_cost']:.6f}")

        # Cache stats
        print_section("Cache Performance")
        cache_stats = self.cost_tracker.get_cache_stats()
        print(f"Cache entries: {cache_stats['total_entries']}")
        print(f"Cache hits: {cache_stats['total_hits']}")
        print(f"Hit rate: {cache_stats['hit_rate_percent']:.1f}%")
        print(f"Cost savings: ${cache_stats['total_savings']:.6f}")

    def show_history(self, limit: int = 20) -> None:
        """Display recent request history."""
        print_header(f"Recent Request History (last {limit})")

        history = self.cost_tracker.get_request_history(limit)

        if not history:
            print_info("No requests in history")
            return

        for i, req in enumerate(history, 1):
            print(f"\n{Colors.BOLD}{i}. {req['timestamp']}{Colors.END}")
            print(f"   Prompt: {req['prompt_preview']}")
            print(f"   Provider: {req['provider']}/{req['model']}")
            print(f"   Complexity: {req['complexity']}")
            print(f"   Cost: ${req['cost']:.6f}")

    def show_insights(self) -> None:
        """Display learning insights."""
        print_header("Learning Insights")

        if not hasattr(self.router, "analyzer") or not self.router.analyzer:
            print_warning("Intelligent routing not enabled. Need more historical data.")
            print_info("Use 'test' mode to generate data with quality ratings")
            return

        insights = self.router.analyzer.get_insights()

        # Overall
        print_section("Overall")
        print(f"Unique queries: {insights['overall']['unique_queries']}")
        print(f"Total requests: {insights['overall']['total_requests']}")
        print(f"Rated responses: {insights['overall']['rated_responses']}")

        learning_active = insights["overall"]["rated_responses"] >= 5
        status = (
            f"{Colors.GREEN}ACTIVE{Colors.END}"
            if learning_active
            else f"{Colors.YELLOW}INACTIVE{Colors.END}"
        )
        print(f"Learning status: {status}")

        if not learning_active:
            print_info(
                f"Need {5 - insights['overall']['rated_responses']} more rated responses "
                "to activate learning"
            )

        # Provider performance
        if insights["by_provider"]:
            print_section("Provider Performance")
            for provider in insights["by_provider"]:
                print(f"\n{Colors.BOLD}{provider['provider']}{Colors.END}:")
                print(f"  Requests: {provider['requests']}")
                if provider["avg_quality"]:
                    print(f"  Avg quality: {provider['avg_quality']:.2f}")
                print(f"  Avg cost: ${provider['avg_cost']:.6f}")
                if provider["upvotes"] or provider["downvotes"]:
                    print(f"  Votes: {provider['upvotes']} 👍 / {provider['downvotes']} 👎")

        # Complexity breakdown
        if insights["by_complexity"]:
            print_section("By Complexity")
            for complexity in insights["by_complexity"]:
                print(f"\n{Colors.BOLD}{complexity['complexity']}{Colors.END}:")
                print(f"  Requests: {complexity['requests']}")
                if complexity["avg_quality"]:
                    print(f"  Avg quality: {complexity['avg_quality']:.2f}")
                print(f"  Avg cost: ${complexity['avg_cost']:.6f}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI Cost Optimizer Interactive Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "command", choices=["test", "stats", "history", "insights"], help="Command to execute"
    )

    parser.add_argument(
        "--limit", type=int, default=20, help="Number of history entries to show (default: 20)"
    )

    args = parser.parse_args()

    tester = CLITester()

    try:
        if args.command == "test":
            asyncio.run(tester.test_interactive())
        elif args.command == "stats":
            tester.show_stats()
        elif args.command == "history":
            tester.show_history(args.limit)
        elif args.command == "insights":
            tester.show_insights()
    except KeyboardInterrupt:
        print_success("\n\nExited by user")
    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

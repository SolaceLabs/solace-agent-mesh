#!/usr/bin/env python3
"""
SAM Apps Feature - Frontend Structure Validation Test

This test validates that all frontend components, pages, hooks, and types
have been created correctly and are properly integrated.

Tests:
1. Component files exist
2. TypeScript compilation succeeds
3. Router configuration present
4. Type definitions present
5. Import/export structure valid
"""

import subprocess
from pathlib import Path
import sys

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}ℹ {msg}{RESET}")

def print_section(msg):
    print(f"\n{YELLOW}{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}{RESET}\n")

class FrontendValidator:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.frontend_dir = self.root_dir / "client" / "webui" / "frontend"
        self.src_dir = self.frontend_dir / "src"
        self.passed = 0
        self.failed = 0

    def file_exists(self, path: Path, description: str) -> bool:
        """Check if a file exists."""
        if path.exists():
            print_success(f"{description}: {path.relative_to(self.root_dir)}")
            self.passed += 1
            return True
        else:
            print_error(f"{description} NOT FOUND: {path.relative_to(self.root_dir)}")
            self.failed += 1
            return False

    def file_contains(self, path: Path, text: str, description: str) -> bool:
        """Check if a file contains specific text."""
        try:
            content = path.read_text()
            if text in content:
                print_success(f"{description} ✓")
                self.passed += 1
                return True
            else:
                print_error(f"{description} ✗ (text not found)")
                self.failed += 1
                return False
        except Exception as e:
            print_error(f"{description} ✗ (error: {e})")
            self.failed += 1
            return False

    def run_test_1_page_components(self):
        """Test 1: Verify all page components exist."""
        print_section("Test 1: Page Components")

        pages_dir = self.src_dir / "lib" / "components" / "pages"

        self.file_exists(pages_dir / "AppsPage.tsx", "Apps list page")
        self.file_exists(pages_dir / "AppEditorPage.tsx", "App editor page")
        self.file_exists(pages_dir / "AppViewPage.tsx", "App view page")

    def run_test_2_app_components(self):
        """Test 2: Verify app-specific components."""
        print_section("Test 2: App Components")

        apps_dir = self.src_dir / "lib" / "components" / "apps"

        self.file_exists(apps_dir / "AppCard.tsx", "App card component")
        self.file_exists(apps_dir / "AppPreview.tsx", "App preview component")

    def run_test_3_hooks(self):
        """Test 3: Verify React hooks."""
        print_section("Test 3: React Hooks")

        hooks_dir = self.src_dir / "lib" / "hooks"

        self.file_exists(hooks_dir / "useApps.ts", "useApps hook")
        self.file_exists(hooks_dir / "useApp.ts", "useApp hook")

    def run_test_4_types(self):
        """Test 4: Verify type definitions."""
        print_section("Test 4: Type Definitions")

        types_dir = self.src_dir / "lib" / "types"

        self.file_exists(types_dir / "app.ts", "App type definitions")

    def run_test_5_router_integration(self):
        """Test 5: Verify router integration."""
        print_section("Test 5: Router Integration")

        router_path = self.src_dir / "router.tsx"

        if self.file_exists(router_path, "Router configuration"):
            # Check for app routes (React Router uses "apps" without leading slash for child routes)
            self.file_contains(router_path, 'path: "apps"', "Apps route exists")
            self.file_contains(router_path, "AppsPage", "AppsPage imported")
            self.file_contains(router_path, "AppEditorPage", "AppEditorPage route exists")
            self.file_contains(router_path, "AppViewPage", "AppViewPage route exists")

    def run_test_6_typescript_compilation(self):
        """Test 6: Verify TypeScript compilation."""
        print_section("Test 6: TypeScript Compilation")

        print_info("Running TypeScript compiler (npx tsc --noEmit)...")

        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=self.frontend_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                print_success("TypeScript compilation successful (no errors)")
                self.passed += 1
            else:
                print_error(f"TypeScript compilation failed:")
                print(result.stdout)
                print(result.stderr)
                self.failed += 1
        except subprocess.TimeoutExpired:
            print_error("TypeScript compilation timed out")
            self.failed += 1
        except Exception as e:
            print_error(f"TypeScript compilation error: {e}")
            self.failed += 1

    def run_test_7_component_structure(self):
        """Test 7: Verify component implementation details."""
        print_section("Test 7: Component Implementation")

        # Check AppsPage
        apps_page = self.src_dir / "lib" / "components" / "pages" / "AppsPage.tsx"
        self.file_contains(apps_page, "useApps", "AppsPage uses useApps hook")
        self.file_contains(apps_page, "AppCard", "AppsPage uses AppCard component")

        # Check AppEditorPage
        editor_page = self.src_dir / "lib" / "components" / "pages" / "AppEditorPage.tsx"
        self.file_contains(editor_page, "useApp", "AppEditorPage uses useApp hook")
        self.file_contains(editor_page, "useParams", "AppEditorPage uses useParams")

        # Check AppViewPage
        view_page = self.src_dir / "lib" / "components" / "pages" / "AppViewPage.tsx"
        self.file_contains(view_page, "useParams", "AppViewPage uses useParams")

    def run_test_8_export_structure(self):
        """Test 8: Verify export structure."""
        print_section("Test 8: Export Structure")

        # Check if components are exported
        pages_index = self.src_dir / "lib" / "components" / "pages" / "index.ts"
        if self.file_exists(pages_index, "Pages index file"):
            self.file_contains(pages_index, "AppsPage", "AppsPage exported")
            self.file_contains(pages_index, "AppEditorPage", "AppEditorPage exported")
            self.file_contains(pages_index, "AppViewPage", "AppViewPage exported")

        # Check apps components export
        apps_index = self.src_dir / "lib" / "components" / "apps" / "index.ts"
        if self.file_exists(apps_index, "Apps components index file"):
            self.file_contains(apps_index, "AppCard", "AppCard exported")
            self.file_contains(apps_index, "AppPreview", "AppPreview exported")

    def run_all_tests(self):
        """Run all validation tests."""
        print(f"\n{BLUE}{'='*70}")
        print("  SAM Apps Feature - Frontend Structure Validation")
        print(f"{'='*70}{RESET}\n")

        print_info(f"Frontend directory: {self.frontend_dir}")
        print_info(f"Source directory: {self.src_dir}")
        print()

        self.run_test_1_page_components()
        self.run_test_2_app_components()
        self.run_test_3_hooks()
        self.run_test_4_types()
        self.run_test_5_router_integration()
        self.run_test_6_typescript_compilation()
        self.run_test_7_component_structure()
        self.run_test_8_export_structure()

        # Summary
        print_section("Test Summary")
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"Total tests: {total}")
        print(f"{GREEN}Passed: {self.passed}{RESET}")
        print(f"{RED}Failed: {self.failed}{RESET}")
        print(f"Success rate: {success_rate:.1f}%\n")

        if self.failed == 0:
            print(f"{GREEN}{'='*70}")
            print("  ✓ ALL FRONTEND VALIDATION TESTS PASSED")
            print(f"{'='*70}{RESET}\n")
            return True
        else:
            print(f"{RED}{'='*70}")
            print(f"  ✗ {self.failed} TEST(S) FAILED")
            print(f"{'='*70}{RESET}\n")
            return False

def main():
    validator = FrontendValidator()
    success = validator.run_all_tests()

    if success:
        print_info("Frontend structure is complete and valid!")
        print_info("Next steps:")
        print("  1. Start HTTP/SSE gateway for integration testing")
        print("  2. Build frontend with: npm run build")
        print("  3. Test UI in browser")
        print()
        sys.exit(0)
    else:
        print_error("Frontend validation failed. Please review errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

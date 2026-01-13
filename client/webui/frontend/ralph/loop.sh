#!/bin/bash
# Ralph Wiggum Loop Script
# Usage: ./loop.sh [plan] [max_iterations]

# Get the project root (parent of ralph directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Ralph directory: $SCRIPT_DIR"
echo "Project root: $PROJECT_ROOT"
echo ""

if [ "$1" = "plan" ]; then
  MODE="plan"
  PROMPT_FILE="$SCRIPT_DIR/PROMPT_plan.md"
  MAX_ITERATIONS=${2:-1}
  echo "=== PLANNING MODE ==="
elif [[ "$1" =~ ^[0-9]+$ ]]; then
  MODE="build"
  PROMPT_FILE="$SCRIPT_DIR/PROMPT_build.md"
  MAX_ITERATIONS=$1
  echo "=== BUILD MODE - $MAX_ITERATIONS iterations ==="
else
  MODE="build"
  PROMPT_FILE="$SCRIPT_DIR/PROMPT_build.md"
  MAX_ITERATIONS=999999
  echo "=== BUILD MODE - unlimited iterations ==="
fi

ITERATION=0

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  ITERATION_START=$(date +%s)

  echo ""
  echo "=========================================="
  echo "   Iteration $((ITERATION + 1)) / $MAX_ITERATIONS"
  echo "=========================================="
  echo ""

  # Show current task from implementation plan
  echo "📋 Current Implementation Plan:"
  if [ -f "$SCRIPT_DIR/IMPLEMENTATION_PLAN.md" ]; then
    FIRST_TASK=$(grep "^- \[" "$SCRIPT_DIR/IMPLEMENTATION_PLAN.md" | head -1)
    TASK_COUNT=$(grep -c "^- \[" "$SCRIPT_DIR/IMPLEMENTATION_PLAN.md" || echo "0")
    echo "   ➡️  Next task: $FIRST_TASK"
    echo "   📊 Remaining tasks: $TASK_COUNT"
  else
    echo "   ⚠️  No implementation plan found"
  fi
  echo ""

  # Save output to log file for debugging
  LOG_FILE="$SCRIPT_DIR/iteration_$((ITERATION + 1)).log"
  TOKEN_FILE="$SCRIPT_DIR/.tokens_iteration_$((ITERATION + 1))"

  echo "🤖 Running Claude..."
  echo "   📝 Log file: iteration_$((ITERATION + 1)).log"
  echo "   ⏰ Start time: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "   🔧 Model: sonnet"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Run claude from the project root, but use prompt file from ralph directory
  cd "$PROJECT_ROOT"

  # Run with verbose output
  cat "$PROMPT_FILE" | claude --print \
    --dangerously-skip-permissions \
    --model sonnet \
    --verbose \
    2>&1 | tee "$LOG_FILE"

  EXIT_CODE=$?
  ITERATION_END=$(date +%s)
  ITERATION_TIME=$((ITERATION_END - ITERATION_START))

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "   ⏰ End time: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "   ⏱️  Duration: ${ITERATION_TIME}s"
  echo ""

  # Try to extract token usage from log
  if [ -f "$LOG_FILE" ]; then
    INPUT_TOKENS=$(grep -oE "input.*tokens?.*[0-9,]+" "$LOG_FILE" | grep -oE "[0-9,]+" | tail -1 | tr -d ',')
    OUTPUT_TOKENS=$(grep -oE "output.*tokens?.*[0-9,]+" "$LOG_FILE" | grep -oE "[0-9,]+" | tail -1 | tr -d ',')

    # Alternative patterns for token detection
    if [ -z "$INPUT_TOKENS" ]; then
      INPUT_TOKENS=$(grep -oE "[0-9,]+.*input" "$LOG_FILE" | grep -oE "[0-9,]+" | head -1 | tr -d ',')
    fi
    if [ -z "$OUTPUT_TOKENS" ]; then
      OUTPUT_TOKENS=$(grep -oE "[0-9,]+.*output" "$LOG_FILE" | grep -oE "[0-9,]+" | head -1 | tr -d ',')
    fi

    # Store tokens for cumulative tracking
    echo "$INPUT_TOKENS $OUTPUT_TOKENS" > "$TOKEN_FILE"

    if [ -n "$INPUT_TOKENS" ] && [ -n "$OUTPUT_TOKENS" ]; then
      # Calculate costs (Sonnet: $3/M input, $15/M output)
      INPUT_COST=$(echo "scale=4; $INPUT_TOKENS * 3 / 1000000" | bc 2>/dev/null || echo "0")
      OUTPUT_COST=$(echo "scale=4; $OUTPUT_TOKENS * 15 / 1000000" | bc 2>/dev/null || echo "0")
      TOTAL_COST=$(echo "scale=4; $INPUT_COST + $OUTPUT_COST" | bc 2>/dev/null || echo "0")

      echo "📊 Token Usage (this iteration):"
      echo "   📥 Input tokens:  $(printf "%'d" $INPUT_TOKENS) (~\$${INPUT_COST})"
      echo "   📤 Output tokens: $(printf "%'d" $OUTPUT_TOKENS) (~\$${OUTPUT_COST})"
      echo "   💰 Iteration cost: ~\$${TOTAL_COST}"
      echo ""

      # Calculate cumulative tokens
      TOTAL_INPUT=0
      TOTAL_OUTPUT=0
      for token_file in "$SCRIPT_DIR"/.tokens_iteration_*; do
        if [ -f "$token_file" ]; then
          read -r inp out < "$token_file"
          TOTAL_INPUT=$((TOTAL_INPUT + ${inp:-0}))
          TOTAL_OUTPUT=$((TOTAL_OUTPUT + ${out:-0}))
        fi
      done

      if [ $TOTAL_INPUT -gt 0 ] || [ $TOTAL_OUTPUT -gt 0 ]; then
        CUMULATIVE_INPUT_COST=$(echo "scale=4; $TOTAL_INPUT * 3 / 1000000" | bc 2>/dev/null || echo "0")
        CUMULATIVE_OUTPUT_COST=$(echo "scale=4; $TOTAL_OUTPUT * 15 / 1000000" | bc 2>/dev/null || echo "0")
        CUMULATIVE_COST=$(echo "scale=4; $CUMULATIVE_INPUT_COST + $CUMULATIVE_OUTPUT_COST" | bc 2>/dev/null || echo "0")

        echo "📈 Cumulative Token Usage (all iterations):"
        echo "   📥 Total input:  $(printf "%'d" $TOTAL_INPUT) (~\$${CUMULATIVE_INPUT_COST})"
        echo "   📤 Total output: $(printf "%'d" $TOTAL_OUTPUT) (~\$${CUMULATIVE_OUTPUT_COST})"
        echo "   💰 Total cost: ~\$${CUMULATIVE_COST}"
        echo ""
      fi
    else
      echo "⚠️  Could not extract token usage from output"
      echo "   (Token info may not be available in verbose output)"
      echo ""
    fi
  fi

  if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Claude exited with code $EXIT_CODE"
    echo "   Check log file: $LOG_FILE"
    break
  fi

  # Check if ShareDialog story was changed
  CHANGED_FILES=$(git status --short)
  if echo "$CHANGED_FILES" | grep -q "ShareDialog\.stories\.tsx"; then
    echo "📚 ShareDialog.stories.tsx detected in changes"
    echo "   ⚠️  Reminder: npx vitest --project=storybook src/stories/ShareDialog.stories.tsx should have run"
    echo ""
  fi

  # Show what changed
  echo "📝 Changes made this iteration:"
  if [ -n "$CHANGED_FILES" ]; then
    echo "$CHANGED_FILES" | head -10 | while read -r line; do
      echo "   $line"
    done
    CHANGE_COUNT=$(echo "$CHANGED_FILES" | wc -l | xargs)
    if [ "$CHANGE_COUNT" -gt 10 ]; then
      echo "   ... and $((CHANGE_COUNT - 10)) more files"
    fi
  else
    echo "   (No git changes detected)"
  fi
  echo ""

  # Show git log if commit was made
  LAST_COMMIT=$(git log -1 --oneline 2>/dev/null)
  if [ -n "$LAST_COMMIT" ]; then
    echo "✅ Latest commit: $LAST_COMMIT"
    echo ""
  fi

  ITERATION=$((ITERATION + 1))

  if [ $ITERATION -lt $MAX_ITERATIONS ]; then
    echo "⏸️  Pausing for 2 seconds before next iteration..."
    echo ""
    sleep 2
  fi
done

echo ""
echo "=========================================="
echo "   🎉 Ralph Session Complete"
echo "=========================================="
echo "   ✅ Completed iterations: $ITERATION"
echo ""

# Final summary
if [ -f "$SCRIPT_DIR/IMPLEMENTATION_PLAN.md" ]; then
  REMAINING=$(grep -c "^- \[" "$SCRIPT_DIR/IMPLEMENTATION_PLAN.md" || echo "0")
  echo "   📋 Remaining tasks: $REMAINING"
fi

# Calculate total tokens and cost
TOTAL_INPUT=0
TOTAL_OUTPUT=0
for token_file in "$SCRIPT_DIR"/.tokens_iteration_*; do
  if [ -f "$token_file" ]; then
    read -r inp out < "$token_file"
    TOTAL_INPUT=$((TOTAL_INPUT + ${inp:-0}))
    TOTAL_OUTPUT=$((TOTAL_OUTPUT + ${out:-0}))
  fi
done

if [ $TOTAL_INPUT -gt 0 ] || [ $TOTAL_OUTPUT -gt 0 ]; then
  TOTAL_INPUT_COST=$(echo "scale=4; $TOTAL_INPUT * 3 / 1000000" | bc 2>/dev/null || echo "0")
  TOTAL_OUTPUT_COST=$(echo "scale=4; $TOTAL_OUTPUT * 15 / 1000000" | bc 2>/dev/null || echo "0")
  TOTAL_COST=$(echo "scale=4; $TOTAL_INPUT_COST + $TOTAL_OUTPUT_COST" | bc 2>/dev/null || echo "0")

  echo ""
  echo "   💰 Session Summary:"
  echo "      Input tokens:  $(printf "%'d" $TOTAL_INPUT)"
  echo "      Output tokens: $(printf "%'d" $TOTAL_OUTPUT)"
  echo "      Estimated cost: ~\$${TOTAL_COST}"
fi

echo ""
echo "   📊 Git commits: $(git log --oneline --since='1 hour ago' | wc -l | xargs)"
echo ""
echo "=========================================="
echo ""

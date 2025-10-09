if status is-interactive
    # Configure tide prompt items
    set -g tide_left_prompt_items time pwd git
    set -g tide_right_prompt_items status cmd_duration jobs python kubectl toolbox terraform aws
    set -g tide_prompt_add_newline_before true
    set -g tide_cmd_duration_threshold 3000
end

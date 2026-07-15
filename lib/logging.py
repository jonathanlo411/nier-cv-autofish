from datetime import datetime
import os
import statistics
import time

LOG_DIR = "logs"


class FishingLogger:
    """Handles logging of fishing session statistics."""

    def __init__(self, config):
        os.makedirs(LOG_DIR, exist_ok=True)

        self.config = config
        self.session_start = datetime.now()
        self.filename = f"autofishing-{self.session_start.strftime('%Y%m%d-%H%M%S')}.log"
        self.filepath = os.path.join(LOG_DIR, self.filename)

        # Per-cycle stats
        self.cycles = []

        # Accumulated stats
        self.total_catches = 0
        self.total_timeouts = 0
        self.total_fishing_time = 0.0
        self.all_z_values = []
        self.all_fg_values = []

        # Current cycle tracking
        self.cycle_start_time = None
        self.cycle_fg_values = []
        self.cycle_z_values = []
        self.cycle_trigger_z = None
        self.cycle_catch_time = None
        self.cycle_status = None

        self._write_header()

    def _write_header(self):
        """Write the session header with summary placeholder."""
        with open(self.filepath, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("  SESSION SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(
                f"  Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"  Ended:   (session in progress...)\n")
            f.write(f"  Total Session Time: (in progress...)\n")
            f.write(f"  Active Fishing Time: (in progress...)\n")
            f.write(f"  Number of Catches:   (in progress...)\n")
            f.write(f"  Timeouts:            (in progress...)\n")
            f.write(f"  Timeout Rate:        (in progress...)\n")
            f.write(f"  Avg Time per Catch:  (in progress...)\n")
            f.write(f"  Avg Z-Value:         (in progress...)\n")
            f.write(f"  Avg FG-Value:        (in progress...)\n")
            f.write("=" * 80 + "\n\n")
            f.write("PER-CYCLE DETAILS\n")
            f.write("-" * 80 + "\n")
            f.write(
                f"{'Cycle':<8} {'Status':<12} {'Catch Time(s)':<16} {'Avg FG':<12} {'Avg Z':<12} {'Trigger Z':<12}\n")
            f.write("-" * 80 + "\n")

    def start_cycle(self):
        """Call at the beginning of detection (after cast)."""
        self.cycle_start_time = time.time()
        self.cycle_fg_values = []
        self.cycle_z_values = []
        self.cycle_trigger_z = None
        self.cycle_catch_time = None
        self.cycle_status = "timeout"

    def log_frame(self, fg_count, z_score):
        """Log a frame's metrics during detection."""
        self.cycle_fg_values.append(fg_count)
        if z_score is not None:
            self.cycle_z_values.append(z_score)

    def log_bite(self, trigger_z):
        """Call when a bite is detected."""
        self.cycle_catch_time = time.time() - self.cycle_start_time
        self.cycle_trigger_z = trigger_z
        self.cycle_status = "complete"
        self._finalize_cycle()

    def log_timeout(self):
        """Call when a cycle times out."""
        self.cycle_catch_time = self.config.get('catch_timeout', 45.0)
        self.cycle_trigger_z = 0
        self.cycle_status = "timeout"
        self._finalize_cycle()

    def _finalize_cycle(self):
        """Write cycle data and update accumulated stats."""
        self.total_catches += 1

        if self.cycle_status == "timeout":
            self.total_timeouts += 1
        else:
            self.total_fishing_time += self.cycle_catch_time
            self.all_z_values.extend(self.cycle_z_values)
            self.all_fg_values.extend(self.cycle_fg_values)

        avg_fg = statistics.mean(
            self.cycle_fg_values) if self.cycle_fg_values else 0
        avg_z = statistics.mean(
            self.cycle_z_values) if self.cycle_z_values else 0

        cycle_data = {
            'cycle_num': self.total_catches,
            'status': self.cycle_status,
            'catch_time': self.cycle_catch_time,
            'avg_fg': avg_fg,
            'avg_z': avg_z,
            'trigger_z': self.cycle_trigger_z if self.cycle_trigger_z else 0,
        }
        self.cycles.append(cycle_data)
        import os


LOG_DIR = "logs"


class FishingLogger:
    """Handles logging of fishing session statistics."""

    def __init__(self, config):
        os.makedirs(LOG_DIR, exist_ok=True)

        self.config = config
        self.session_start = datetime.now()
        self.filename = f"autofishing-{self.session_start.strftime('%Y%m%d-%H%M%S')}.log"
        self.filepath = os.path.join(LOG_DIR, self.filename)

        # Per-cycle stats
        self.cycles = []

        # Accumulated stats
        self.total_catches = 0
        self.total_timeouts = 0
        self.total_fishing_time = 0.0
        self.all_z_values = []
        self.all_fg_values = []

        # Current cycle tracking
        self.cycle_start_time = None
        self.cycle_fg_values = []
        self.cycle_z_values = []
        self.cycle_trigger_z = None
        self.cycle_catch_time = None
        self.cycle_status = None

        self._write_header()

    def _write_header(self):
        """Write the session header with summary placeholder."""
        with open(self.filepath, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("  SESSION SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(
                f"  Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"  Ended:   (session in progress...)\n")
            f.write(f"  Total Session Time: (in progress...)\n")
            f.write(f"  Active Fishing Time: (in progress...)\n")
            f.write(f"  Number of Catches:   (in progress...)\n")
            f.write(f"  Timeouts:            (in progress...)\n")
            f.write(f"  Timeout Rate:        (in progress...)\n")
            f.write(f"  Avg Time per Catch:  (in progress...)\n")
            f.write(f"  Avg Z-Value:         (in progress...)\n")
            f.write(f"  Avg FG-Value:        (in progress...)\n")
            f.write("=" * 80 + "\n\n")
            f.write("PER-CYCLE DETAILS\n")
            f.write("-" * 80 + "\n")
            f.write(
                f"{'Cycle':<8} {'Status':<12} {'Catch Time(s)':<16} {'Avg FG':<12} {'Avg Z':<12} {'Trigger Z':<12}\n")
            f.write("-" * 80 + "\n")

    def start_cycle(self):
        """Call at the beginning of detection (after cast)."""
        self.cycle_start_time = time.time()
        self.cycle_fg_values = []
        self.cycle_z_values = []
        self.cycle_trigger_z = None
        self.cycle_catch_time = None
        self.cycle_status = "timeout"

    def log_frame(self, fg_count, z_score):
        """Log a frame's metrics during detection."""
        self.cycle_fg_values.append(fg_count)
        if z_score is not None:
            self.cycle_z_values.append(z_score)

    def log_bite(self, trigger_z):
        """Call when a bite is detected. Returns cycle_data dict."""
        self.cycle_catch_time = time.time() - self.cycle_start_time
        self.cycle_trigger_z = trigger_z
        self.cycle_status = "complete"
        return self._finalize_cycle()

    def log_timeout(self):
        """Call when a cycle times out. Returns cycle_data dict."""
        self.cycle_catch_time = self.config.get('catch_timeout', 45.0)
        self.cycle_trigger_z = 0
        self.cycle_status = "timeout"
        return self._finalize_cycle()

    def _finalize_cycle(self):
        """Write cycle data, update accumulated stats, return cycle_data dict."""
        self.total_catches += 1

        if self.cycle_status == "timeout":
            self.total_timeouts += 1
        else:
            self.total_fishing_time += self.cycle_catch_time
            self.all_z_values.extend(self.cycle_z_values)
            self.all_fg_values.extend(self.cycle_fg_values)

        avg_fg = statistics.mean(
            self.cycle_fg_values) if self.cycle_fg_values else 0
        avg_z = statistics.mean(
            self.cycle_z_values) if self.cycle_z_values else 0

        cycle_data = {
            'cycle_num': self.total_catches,
            'status': self.cycle_status,
            'catch_time': self.cycle_catch_time,
            'avg_fg': avg_fg,
            'avg_z': avg_z,
            'trigger_z': self.cycle_trigger_z if self.cycle_trigger_z else 0,
        }
        self.cycles.append(cycle_data)

        # Write cycle detail to log
        with open(self.filepath, 'a') as f:
            f.write(f"{cycle_data['cycle_num']:<8} "
                    f"{cycle_data['status']:<12} "
                    f"{cycle_data['catch_time']:<16.2f} "
                    f"{cycle_data['avg_fg']:<12.1f} "
                    f"{cycle_data['avg_z']:<12.2f} "
                    f"{cycle_data['trigger_z']:<12.2f}\n")

        return cycle_data

    def write_summary(self):
        """Rewrite the file with final summary at the top."""
        session_end = datetime.now()
        total_session_time = (session_end - self.session_start).total_seconds()

        valid_catches = self.total_catches - self.total_timeouts
        avg_catch_time = (
            self.total_fishing_time /
            valid_catches) if valid_catches > 0 else 0
        avg_z = statistics.mean(self.all_z_values) if self.all_z_values else 0
        avg_fg = statistics.mean(
            self.all_fg_values) if self.all_fg_values else 0
        timeout_rate = (
            self.total_timeouts /
            self.total_catches *
            100) if self.total_catches > 0 else 0

        # Read existing file content
        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        # Find where the per-cycle details start
        cycle_start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "PER-CYCLE DETAILS":
                cycle_start_idx = i
                break

        # Rebuild the file with updated summary at top
        with open(self.filepath, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("  SESSION SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(
                f"  Started:             {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(
                f"  Ended:               {session_end.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(
                f"  Total Session Time:  {total_session_time:.1f}s ({total_session_time/60:.1f} min)\n")
            f.write(f"  Active Fishing Time: {self.total_fishing_time:.1f}s\n")
            f.write(f"  Number of Catches:   {self.total_catches}\n")
            f.write(f"  Successful:          {valid_catches}\n")
            f.write(f"  Timeouts:            {self.total_timeouts}\n")
            f.write(f"  Timeout Rate:        {timeout_rate:.1f}%\n")
            f.write(
                f"  Avg Time per Catch:  {avg_catch_time:.1f}s (successful only)\n")
            f.write(f"  Avg Z-Value:         {avg_z:.2f}\n")
            f.write(f"  Avg FG-Value:        {avg_fg:.1f}\n")
            f.write("=" * 80 + "\n")

            # Config details
            cfg = self.config
            f.write(
                f"  Monitor:             {cfg.get('monitor_width')}x{cfg.get('monitor_height')} at ({cfg.get('monitor_left')},{cfg.get('monitor_top')})\n")
            f.write(f"  FPS Target:          {cfg.get('fps_target')}\n")
            f.write(f"  Crop Size:           {cfg.get('crop_size')}px\n")
            f.write(f"  Spike Z Threshold:   {cfg.get('spike_z_thresh')}\n")
            f.write(f"  Min Spike Sec:       {cfg.get('min_spike_sec')}\n")
            f.write(
                f"  Baseline Window Sec: {cfg.get('baseline_window_sec')}\n")
            f.write(f"  Cooldown Sec:        {cfg.get('cooldown_sec')}\n")
            f.write(f"  History:             {cfg.get('history')}\n")
            f.write(f"  Var Threshold:       {cfg.get('var_threshold')}\n")
            f.write(f"  Catch Timeout:       {cfg.get('catch_timeout')}s\n")
            f.write(
                f"  Look-down Duration:  {cfg.get('look_down_duration')}s\n")
            f.write(f"  Look-down Speed:     {cfg.get('look_down_speed')}\n")
            f.write(
                f"  Reset-up Duration:   {cfg.get('reset_up_duration')}s\n")
            f.write(f"  Reset-up Speed:      {cfg.get('reset_up_speed')}\n")
            f.write("=" * 80 + "\n\n")

            # Write the per-cycle details section
            if cycle_start_idx > 0:
                f.writelines(lines[cycle_start_idx:])

        return {
            'total_session_time': total_session_time,
            'total_fishing_time': self.total_fishing_time,
            'total_catches': self.total_catches,
            'valid_catches': valid_catches,
            'total_timeouts': self.total_timeouts,
            'timeout_rate': timeout_rate,
            'avg_catch_time': avg_catch_time,
            'avg_z': avg_z,
            'avg_fg': avg_fg,
        }

    def print_summary(self):
        """Print summary to console."""
        summary = self.write_summary()
        print("\n" + "=" * 60)
        print("  SESSION SUMMARY")
        print("=" * 60)
        print(
            f"  Started:          {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"  Total time:       {summary['total_session_time']:.0f}s ({summary['total_session_time']/60:.1f} min)")
        print(f"  Fishing time:     {summary['total_fishing_time']:.0f}s")
        print(f"  Total cycles:     {summary['total_catches']}")
        print(f"  Successful:       {summary['valid_catches']}")
        print(f"  Timeouts:         {summary['total_timeouts']}")
        print(f"  Timeout rate:     {summary['timeout_rate']:.1f}%")
        print(
            f"  Avg time/catch:   {summary['avg_catch_time']:.1f}s (successful)")
        print(f"  Avg Z-Value:      {summary['avg_z']:.2f}")
        print(f"  Avg FG-Value:     {summary['avg_fg']:.1f}")
        print(f"  Log saved to:     {self.filepath}")
        print("=" * 60)
        # Write cycle detail to log
        with open(self.filepath, 'a') as f:
            f.write(f"{cycle_data['cycle_num']:<8} "
                    f"{cycle_data['status']:<12} "
                    f"{cycle_data['catch_time']:<16.2f} "
                    f"{cycle_data['avg_fg']:<12.1f} "
                    f"{cycle_data['avg_z']:<12.2f} "
                    f"{cycle_data['trigger_z']:<12.2f}\n")

    def write_summary(self):
        """Rewrite the file with final summary at the top."""
        session_end = datetime.now()
        total_session_time = (session_end - self.session_start).total_seconds()

        valid_catches = self.total_catches - self.total_timeouts
        avg_catch_time = (
            self.total_fishing_time /
            valid_catches) if valid_catches > 0 else 0
        avg_z = statistics.mean(self.all_z_values) if self.all_z_values else 0
        avg_fg = statistics.mean(
            self.all_fg_values) if self.all_fg_values else 0
        timeout_rate = (
            self.total_timeouts /
            self.total_catches *
            100) if self.total_catches > 0 else 0

        # Read existing file content
        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        # Find where the per-cycle details start
        cycle_start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "PER-CYCLE DETAILS":
                cycle_start_idx = i
                break

        # Rebuild the file with updated summary at top
        with open(self.filepath, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("  SESSION SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(
                f"  Started:             {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(
                f"  Ended:               {session_end.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(
                f"  Total Session Time:  {total_session_time:.1f}s ({total_session_time/60:.1f} min)\n")
            f.write(f"  Active Fishing Time: {self.total_fishing_time:.1f}s\n")
            f.write(f"  Number of Catches:   {self.total_catches}\n")
            f.write(f"  Successful:          {valid_catches}\n")
            f.write(f"  Timeouts:            {self.total_timeouts}\n")
            f.write(f"  Timeout Rate:        {timeout_rate:.1f}%\n")
            f.write(
                f"  Avg Time per Catch:  {avg_catch_time:.1f}s (successful only)\n")
            f.write(f"  Avg Z-Value:         {avg_z:.2f}\n")
            f.write(f"  Avg FG-Value:        {avg_fg:.1f}\n")
            f.write("=" * 80 + "\n")

            # Config details
            cfg = self.config
            f.write(
                f"  Monitor:             {cfg.get('monitor_width')}x{cfg.get('monitor_height')} at ({cfg.get('monitor_left')},{cfg.get('monitor_top')})\n")
            f.write(f"  FPS Target:          {cfg.get('fps_target')}\n")
            f.write(f"  Crop Size:           {cfg.get('crop_size')}px\n")
            f.write(f"  Spike Z Threshold:   {cfg.get('spike_z_thresh')}\n")
            f.write(f"  Min Spike Sec:       {cfg.get('min_spike_sec')}\n")
            f.write(
                f"  Baseline Window Sec: {cfg.get('baseline_window_sec')}\n")
            f.write(f"  Cooldown Sec:        {cfg.get('cooldown_sec')}\n")
            f.write(f"  History:             {cfg.get('history')}\n")
            f.write(f"  Var Threshold:       {cfg.get('var_threshold')}\n")
            f.write(f"  Catch Timeout:       {cfg.get('catch_timeout')}s\n")
            f.write(
                f"  Look-down Duration:  {cfg.get('look_down_duration')}s\n")
            f.write(f"  Look-down Speed:     {cfg.get('look_down_speed')}\n")
            f.write(
                f"  Reset-up Duration:   {cfg.get('reset_up_duration')}s\n")
            f.write(f"  Reset-up Speed:      {cfg.get('reset_up_speed')}\n")
            f.write("=" * 80 + "\n\n")

            # Write the per-cycle details section
            if cycle_start_idx > 0:
                f.writelines(lines[cycle_start_idx:])

        return {
            'total_session_time': total_session_time,
            'total_fishing_time': self.total_fishing_time,
            'total_catches': self.total_catches,
            'valid_catches': valid_catches,
            'total_timeouts': self.total_timeouts,
            'timeout_rate': timeout_rate,
            'avg_catch_time': avg_catch_time,
            'avg_z': avg_z,
            'avg_fg': avg_fg,
        }

    def print_summary(self):
        """Print summary to console."""
        summary = self.write_summary()
        print("\n" + "=" * 60)
        print("  SESSION SUMMARY")
        print("=" * 60)
        print(
            f"  Started:          {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"  Total time:       {summary['total_session_time']:.0f}s ({summary['total_session_time']/60:.1f} min)")
        print(f"  Fishing time:     {summary['total_fishing_time']:.0f}s")
        print(f"  Total cycles:     {summary['total_catches']}")
        print(f"  Successful:       {summary['valid_catches']}")
        print(f"  Timeouts:         {summary['total_timeouts']}")
        print(f"  Timeout rate:     {summary['timeout_rate']:.1f}%")
        print(
            f"  Avg time/catch:   {summary['avg_catch_time']:.1f}s (successful)")
        print(f"  Avg Z-Value:      {summary['avg_z']:.2f}")
        print(f"  Avg FG-Value:     {summary['avg_fg']:.1f}")
        print(f"  Log saved to:     {self.filepath}")
        print("=" * 60)

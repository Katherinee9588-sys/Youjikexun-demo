from __future__ import annotations

from app.models.hardware import MAX30102SampleCreate


def should_forward_max30102_sample(sample: MAX30102SampleCreate) -> bool:
    """Forward only an explicitly valid measurement to local persistence.

    ``warming_up``, ``unstable`` and ``finger_absent`` remain useful on the
    device monitor, but they are not health observations for the user record.
    """

    return sample.signal_quality == "valid"

"""Server-rendered forms for CryoCheck accounts and personal settings."""

from __future__ import annotations

import re
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Regexp,
    ValidationError,
)

from app.services.settings import TYPE1_FLUID_OPTIONS, TYPE4_FLUID_OPTIONS


ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _trim(value: str | None) -> str:
    return value.strip() if value else ""


def _positive_rate(form, field) -> None:
    del form
    if (
        field.data is None
        or not field.data.is_finite()
        or field.data < Decimal("0.000001")
    ):
        raise ValidationError("Enter a value greater than 0.")
    if field.data.as_tuple().exponent < -6:
        raise ValidationError("Use no more than six decimal places.")


class CompactDecimalField(DecimalField):
    """Render stored decimals without insignificant trailing zeroes."""

    def _value(self) -> str:
        if self.raw_data:
            return self.raw_data[0]
        if self.data is None:
            return ""
        return format(self.data.normalize(), "f")


class RegisterForm(FlaskForm):
    """Create one optional local account."""

    username = StringField(
        "Account name",
        filters=[_trim],
        validators=[
            DataRequired(),
            Length(min=3, max=40),
            Regexp(
                ACCOUNT_NAME_PATTERN,
                message=(
                    "Use only letters, numbers, underscores, and hyphens."
                ),
            ),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    """Authenticate one existing account."""

    username = StringField(
        "Account name",
        filters=[_trim],
        validators=[DataRequired(), Length(min=3, max=40)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(max=128)],
    )
    remember = BooleanField("Keep me signed in", default=True)
    next_url = HiddenField()
    submit = SubmitField("Sign In")


class SettingsForm(FlaskForm):
    """Edit the signed-in user's private settings record."""

    late_entry_threshold_hours = SelectField(
        "Late-entry threshold",
        choices=((24, "24 hours"), (48, "48 hours")),
        coerce=int,
        validators=[InputRequired()],
    )
    type1_fluid = SelectField(
        "Type I fluid",
        choices=tuple((fluid, fluid) for fluid in TYPE1_FLUID_OPTIONS),
        validators=[InputRequired()],
    )
    type4_fluid = SelectField(
        "Type IV fluid",
        choices=tuple((fluid, fluid) for fluid in TYPE4_FLUID_OPTIONS),
        validators=[InputRequired()],
    )
    allowed_gap_minutes = IntegerField(
        "Allowed gap between Type I and Type IV",
        validators=[InputRequired(), NumberRange(min=0, max=99)],
    )
    max_type1_rate_gpm = CompactDecimalField(
        "Maximum Type I adjusted rate",
        places=None,
        validators=[
            InputRequired(),
            _positive_rate,
            NumberRange(max=Decimal("999")),
        ],
    )
    max_type4_rate_gpm = CompactDecimalField(
        "Maximum Type IV adjusted rate",
        places=None,
        validators=[
            InputRequired(),
            _positive_rate,
            NumberRange(max=Decimal("999")),
        ],
    )
    max_event_time_minutes = IntegerField(
        "Maximum event time",
        validators=[InputRequired(), NumberRange(min=1, max=999)],
    )
    include_gap_in_event_time = BooleanField(
        "Include the Type I-to-Type IV gap in event time"
    )
    submit = SubmitField("Save Changes")


class ResetSettingsForm(FlaskForm):
    """Require explicit confirmation before restoring built-in defaults."""

    confirm_reset = BooleanField(
        "I understand this will replace my personal values with Default.",
        validators=[
            DataRequired(message="Confirm the reset before continuing."),
        ],
    )
    submit = SubmitField("Reset to Default")


__all__ = [
    "ACCOUNT_NAME_PATTERN",
    "LoginForm",
    "RegisterForm",
    "ResetSettingsForm",
    "SettingsForm",
]

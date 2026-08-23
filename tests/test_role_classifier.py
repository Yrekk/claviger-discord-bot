from unittest.mock import Mock

import discord

from claviger.policies.guild_policy import GuildPolicy
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleHierarchy


def create_role(
    *,
    name: str,
) -> Mock:
    """Create a mocked Discord role."""
    role = Mock(spec=discord.Role)
    role.name = name

    return role


def create_policy() -> GuildPolicy:
    """Create a guild policy used for role classification tests."""
    return GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Civis Noctis · 18+",
        access_role_prefix="access-",
        salutations_channel_name="salutations",
        adult_rules_channel_name="lex-noctis",
        role_management_enabled=True,
        adult_access_enabled=True,
    )


def create_hierarchy(
    *,
    manageable_roles: list[discord.Role],
) -> RoleHierarchy:
    """Create a role hierarchy with configurable manageable roles."""
    bot_role = create_role(
        name="Claviger",
    )

    return RoleHierarchy(
        bot_role=bot_role,
        trusted_roles=[],
        manageable_roles=manageable_roles,
    )


def test_classifier_identifies_managed_role_types() -> None:
    """Classify member, adult and access roles from the guild policy."""
    classifier = RoleClassifier()

    member = create_role(
        name="Membre",
    )
    adult = create_role(
        name="Civis Noctis · 18+",
    )
    access = create_role(
        name="access-ia-yuri",
    )
    unmanaged = create_role(
        name="Archivum",
    )

    hierarchy = create_hierarchy(
        manageable_roles=[
            member,
            adult,
            access,
            unmanaged,
        ],
    )

    classification = classifier.classify(
        hierarchy,
        create_policy(),
    )

    assert classification.member_roles == [
        member,
    ]
    assert classification.adult_roles == [
        adult,
    ]
    assert classification.access_roles == [
        access,
    ]
    assert classification.unmanaged_roles == [
        unmanaged,
    ]


def test_classifier_keeps_duplicate_fixed_roles_visible() -> None:
    """Keep duplicate fixed roles visible so they can be reported as anomalies."""
    classifier = RoleClassifier()

    first_member = create_role(
        name="Membre",
    )
    second_member = create_role(
        name="Membre",
    )

    hierarchy = create_hierarchy(
        manageable_roles=[
            first_member,
            second_member,
        ],
    )

    classification = classifier.classify(
        hierarchy,
        create_policy(),
    )

    assert classification.member_roles == [
        first_member,
        second_member,
    ]


def test_classifier_uses_policy_role_names_and_prefix() -> None:
    """Classify roles using guild-specific policy values."""
    classifier = RoleClassifier()

    custom_member = create_role(
        name="Citoyen",
    )
    custom_adult = create_role(
        name="Nocturna",
    )
    custom_access = create_role(
        name="custom-yuri",
    )

    policy = GuildPolicy(
        member_role_name="Citoyen",
        adult_role_name="Nocturna",
        access_role_prefix="custom-",
        salutations_channel_name="salutations",
        adult_rules_channel_name="adult-rules",
        role_management_enabled=True,
        adult_access_enabled=True,
    )

    hierarchy = create_hierarchy(
        manageable_roles=[
            custom_member,
            custom_adult,
            custom_access,
        ],
    )

    classification = classifier.classify(
        hierarchy,
        policy,
    )

    assert classification.member_roles == [
        custom_member,
    ]
    assert classification.adult_roles == [
        custom_adult,
    ]
    assert classification.access_roles == [
        custom_access,
    ]
    assert classification.unmanaged_roles == []
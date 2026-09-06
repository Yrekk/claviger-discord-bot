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
    role = Mock(
        spec=discord.Role,
    )
    role.name = name

    return role


def create_policy() -> GuildPolicy:
    """Create a guild policy used for role classification tests."""
    return GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Civis Noctis - 18+",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
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
    """Classify fixed, interest and adult access roles."""
    classifier = RoleClassifier()

    member = create_role(
        name="Membre",
    )
    adult = create_role(
        name="Civis Noctis - 18+",
    )
    interest = create_role(
        name="interest-ia",
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
            interest,
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

    assert classification.interest_roles == [
        interest,
    ]

    assert classification.access_roles == [
        access,
    ]

    assert classification.unmanaged_roles == [
        unmanaged,
    ]


def test_classifier_keeps_duplicate_fixed_roles_visible() -> None:
    """Keep duplicate fixed roles visible for anomaly reporting."""
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


def test_classifier_uses_policy_specific_prefixes() -> None:
    """Use guild-specific interest and adult access prefixes."""
    classifier = RoleClassifier()

    interest = create_role(
        name="topic-ia",
    )
    access = create_role(
        name="private-yuri",
    )

    policy = GuildPolicy(
        member_role_name="Citoyen",
        adult_role_name="Nocturna",
        member_interest_prefix="topic-",
        adult_access_prefix="private-",
        salutations_channel_name="welcome",
        adult_rules_channel_name="rules",
        role_management_enabled=True,
        adult_access_enabled=True,
    )

    hierarchy = create_hierarchy(
        manageable_roles=[
            interest,
            access,
        ],
    )

    classification = classifier.classify(
        hierarchy,
        policy,
    )

    assert classification.interest_roles == [
        interest,
    ]

    assert classification.access_roles == [
        access,
    ]

    assert classification.unmanaged_roles == []


def test_classifier_ignores_empty_prefixes() -> None:
    """Do not classify every role when a configured prefix is empty."""
    classifier = RoleClassifier()

    role = create_role(
        name="Archivum",
    )

    policy = GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Adulte",
        member_interest_prefix="",
        adult_access_prefix="",
        salutations_channel_name="salutations",
        adult_rules_channel_name="adult-rules",
        role_management_enabled=True,
        adult_access_enabled=True,
    )

    hierarchy = create_hierarchy(
        manageable_roles=[
            role,
        ],
    )

    classification = classifier.classify(
        hierarchy,
        policy,
    )

    assert classification.interest_roles == []
    assert classification.access_roles == []
    assert classification.unmanaged_roles == [
        role,
    ]

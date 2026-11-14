from django.db import models


class TaxonomyVersion(models.TextChoices):
    V1 = "v1", "Taxonomy v1"


class PromptVersion(models.TextChoices):
    V1 = "v1", "Classification prompt v1"
    V2 = "v2", "Classification prompt v2"


class Mechanic(models.TextChoices):
    WORDPLAY = "wordplay", "Wordplay"
    ANAGRAM = "anagram", "Anagram"
    BEFORE_AND_AFTER = "before_and_after", "Before and after"
    RHYMING = "rhyming", "Rhyming"
    SPELLING = "spelling", "Spelling"
    HIDDEN_WORD = "hidden_word", "Hidden word"
    REBUS = "rebus", "Rebus"
    NUMERIC = "numeric", "Numeric"
    CATEGORY_CONSTRAINT = "category_constraint", "Category constraint"
    OTHER = "other", "Other mechanic"

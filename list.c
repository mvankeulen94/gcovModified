#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* This is a collection of functions designed to store JSON data
 * in a linked list.
 */
struct List {
    // list pointers
    struct List *next;
    struct List *end;
    struct List *prev;
    struct List *begin;

    // data pointer
    struct ListData *data;
}

struct ListData {
    char *key;
    void *value;
    char *type;
}

void initList(struct List *list) {
    list->next = NULL;
    list->end = NULL;
    list->begin = NULL;
    list->prev = NULL;
    list->data = NULL;
}

int isEmptyList(struct List *list) {
    return list->end == NULL;
}

void addToList(struct List *list, char *key, void *value, char *type) {
    struct List *newList = malloc(sizeof(struct List));
    newList->data = malloc(sizeof(struct ListData));
    newList->data->key = key;
    newList->data->value = value;
    newList->data->type = type;

    if (isEmptyList(list)) {
        list->end = newList;
        list->begin = newList;
    }

    else {
        list->end->next = newList;
        list->end = newList;
    }
} 

void deleteList(struct List *list) {
    struct List *next = current->next;
    struct List *current = list->begin;
    if (strcmp(current->data->type, "list") == 0) {
        deleteList((struct List *) current->data->value);
    }

    free(current->data);
    free(current);

    if (current == list->end) {
        return;
    }

    else {
        deleteList(next);
    }
}


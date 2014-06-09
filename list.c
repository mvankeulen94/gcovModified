#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "list.h"

void initList (struct List *list) {
    list->front = NULL;
    list->back = NULL;
}

int isEmptyList (struct List *list) {
    return list->front == NULL;
}

void addToList (struct List *list, char *key, void *value, char *type) {
    struct Node *newNode = malloc(sizeof(struct Node));
   
    if (isEmptyList(list)) {
        list->front = newNode; 
        list->back = newNode;
    }

    else {
        list->back->next = newNode;
        list->back = newNode;
    }

    newNode->key = key;
    newNode->value = value;
    newNode->type = type;
    newNode->next = NULL;
}

/* Helper function for deleting data stored in a struct List */
static void deleteNode (struct Node *node) {
    int proceed = 1;
    struct Node *next = node->next;
    
    // Determine whether to proceed to next recursive call.
    if (next == NULL) {
        proceed = 0;
    }

    // If node has a List as its value, recursively delete list.
    if (strcmp(node->type, "list") == 0 && 
        !isEmptyList((struct List *) node->value)) {

        deleteList((struct List *) node->value);
    }

    free(node);

    if (proceed) {
        deleteNode(next);
    }
}

void deleteList (struct List *list) {
    deleteNode (list->front);
}

/* Helper function for printing the data in a struct List */
static void printNode (struct Node *node, FILE *file) {
    int proceed = 1;
    struct Node *next = node->next;
    
    // Determine whether to proceed to next recursive call.
    if (next == NULL) {
        proceed = 0;
    }
   
    // If node has List as its value, recursively print list. 
    // Only print list if list is not empty.
    if (strcmp(node->type, "list") == 0 && 
        !isEmptyList((struct List *) node->value)) {

        fprintf(file, "%s: [", node->key);
        printList((struct List *) node->value, file);
        fprintf(file, "]");
    }
    
    if (strcmp(node->type, "int") == 0) {
       fprintf(file, "%s: %d", node->key, *(int *) node->value);
    }

    if (strcmp(node->type, "string") == 0) {
        fprintf(file, "%s: %s", node->key, (char *) node->value);
    }

    if (proceed) {
            // Don't print a comma if node data is an empty list.
            if (strcmp(next->type, "list") != 0 || 
                !isEmptyList((struct List *) next->value)) {
                fprintf(file, ", ");
            }

        printNode(next, file);
    }
}

void printList (struct List *list, FILE *file) {
    printNode (list->front, file);
}

void printDocument (struct List *list, FILE *file) {
    fprintf(file, "\n{");
    printList(list, file);
    fprintf(file, "}\n");
    fflush(file);
}

int main() {
     struct List list;
    initList(&list);
    int x = 1;
    addToList(&list, "h", &x, "int");
    struct List sublist;
    initList(&sublist);
    addToList(&sublist, "hello", "lala", "string");
    addToList(&list, "yo", &sublist, "list");
    addToList(&list, "well", "huh?", "string");
    addToList(&sublist, "what", "heh", "string");
    struct List subsublist;
    initList(&subsublist);
    addToList(&sublist, "nodalist", &subsublist, "list");
//    addToList(&subsublist, "yo", "hi", "string");
    addToList(&list, "lastelement", "weeeee", "string");
    printf("%s\n", (char *) list.front->value);
    struct Node *next = (list.front)->next;
    printf("%s\n", next->type);
    printf("%s\n", (char *) next->next->value);
    printf("%s\n", (char *) (list).back->value);
    printf("COMMENCING LIST PRINT\n");
    printDocument(&list, stdout);

    deleteList(&list);
  return 0;
} 



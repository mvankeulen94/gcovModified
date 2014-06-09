struct Node {
    struct Node *next;

    char *key;
    void *value;
    char *type;
};

struct List {
    struct Node *front;
    struct Node *back;
};

void deleteList(struct List *);
void initList(struct List *list);
int isEmptyList(struct List *list);
void addToList(struct List *list, char *key, void *value, char *type);
void deleteList(struct List *list);
void printList(struct List *list);

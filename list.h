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
void initList(struct List *);
int isEmptyList(struct List *);
void addToList(struct List *, char *, void *, char *);
void deleteList(struct List *);
void printList(struct List *, FILE *);
void printDocument(struct List *, FILE *);

#ifndef AUTODOCGEN_LSP_PROJECT_COMPAT_H
#define AUTODOCGEN_LSP_PROJECT_COMPAT_H

/* LSP-only compatibility shims for legacy TI/CCS style projects. */

#ifndef __interrupt
#define __interrupt
#endif

#ifndef interrupt
#define interrupt
#endif

#ifndef EALLOW
#define EALLOW do {} while (0)
#endif

#ifndef EDIS
#define EDIS do {} while (0)
#endif

#ifndef DINT
#define DINT do {} while (0)
#endif

#ifndef EINT
#define EINT do {} while (0)
#endif

#ifndef asm
#define asm(...)
#endif

#endif
